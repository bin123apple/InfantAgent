import re
import gc
import copy
import torch
from vllm import LLM, SamplingParams
from infant.config import VllmParams
from vllm.distributed.parallel_state import destroy_model_parallel
from infant.util.logger import infant_logger as logger
from infant.agent.memory.memory import Message, CmdRun, IPythonRun

class LLM_OSS_BASED:
    def __init__(self, args: VllmParams):
        logger.info(f'Initializing the api based LLM with the following parameters: {args}')
        self.args = args
        self.model = args.model_oss
        self.tokenizer = args.model_oss
        self.llm = None
        self.sampling_params = SamplingParams(
            n=self.args.sampling_n,
            max_tokens=self.args.max_tokens,
            temperature=self.args.vllm_temperature,
            top_p=self.args.vllm_top_p,
            frequency_penalty=0,
            presence_penalty=0,
            stop=self.args.stop,
        )
        logger.info(f"Finished initializing parameters of the OSS LLM\n"
                    f"Args: {self.args}." )
        
        self.load_model()

    def generate_actions(self, messages: list) -> None:
        """
        Change user input action to observation.
        FIXME: Message class should not be here.
        """
        # run action
        response = self.complete(messages)[0] # Only get the first response
        
        actions = self.parse_response(response) # Only got the first response
        if actions == []: 
            if '<|exit|>' not in response:
                logger.warning(f"<|exit|> is not involved in the response: {response}.")
            action = Message(content=response)
            return action
        else:
            action = self.parse_response(response)[0]
            return action    
    
    def parse_response(self, response) -> list:
        """
        Parse the response and get the commands. 
        The commands should have the same order as shown in the responses.
        FIXME: This logic should be moved outside.

        Args:
            response (str): The response from the model.

        Returns:
            list: The commands to be executed.
        """

        pattern = r"<(execute_bash|execute_ipython)>(.*?)</\1>"
        commands = re.findall(pattern, response, re.DOTALL)

        extracted_commands = []
        
        for command_type, command in commands:
            command = command.strip() 
            if command_type == 'execute_bash':
                extracted_commands.append(CmdRun(command))
            elif command_type == 'execute_ipython':
                extracted_commands.append(IPythonRun(command))
        

        return extracted_commands
    
    
    def load_model(self):
        '''
        Load the model into GPU memory, and keep it.
        '''
        if self.llm is None:
            logger.info(f"Loading model {self.model} into GPU...")
            self.llm = LLM(
                model=self.model,
                tokenizer=self.tokenizer,
                tensor_parallel_size=self.args.tensor_parallel_size,
                gpu_memory_utilization=self.args.gpu_memory_utilization,
                enforce_eager=True,
                max_model_len=self.args.max_model_len,
                disable_custom_all_reduce=True,
                enable_prefix_caching=self.args.enable_prefix_caching,
                trust_remote_code=self.args.trust_remote_code,
            )
            logger.info(f"Model {self.model} loaded into GPU memory")

    def completion(self, messages, stop: list | None = None) -> list:
        '''
        Generate several a list of responses. (Based on the number of sampling_n)
        '''
        # print(f'messages', messages)
        self.load_model()
        sampling_params = copy.deepcopy(self.sampling_params)
        sampling_params.stop = stop
        request_output = self.llm.chat(messages, sampling_params)
        logger.debug(f"Request output: {request_output}")
        self.get_token_count(request_output)
        response_list = []
        for response in request_output[0].outputs:
            response_list.append(response.text)
        return response_list
    

    def get_token_count(self, request_output):
        """
        Get the number of tokens in a list of messages.

        Args:
            messages (list): A list of messages.

        Returns:
            int: The number of tokens.
        """
        outputs = request_output[0].outputs
        number_of_answers = len(outputs)
        input_token_count = len(request_output[0].prompt_token_ids)
        output_token_count = sum(len(output.token_ids) for output in outputs)
        logger.info(
                'Total Input tokens: %.2f | Total Generated tokens: %.2f | Total outputs: %.2f',
                input_token_count,
                output_token_count,
                number_of_answers
            )
        
    
    def clean(self):
        """
        Close the model.
        """
        destroy_model_parallel()
        gc.collect()
        torch.cuda.empty_cache()