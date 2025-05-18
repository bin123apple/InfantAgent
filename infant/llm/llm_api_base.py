import warnings
import inspect
#import asyncio

from functools import partial

with warnings.catch_warnings():
    warnings.simplefilter('ignore')
    import litellm
    litellm.drop_params = True
from litellm import completion as litellm_completion
from litellm import completion_cost as litellm_completion_cost
from litellm.exceptions import (
    APIConnectionError,
    RateLimitError,
    ServiceUnavailableError,
    InternalServerError,
    BadRequestError,
    OpenAIError,
    APIError,
)
from litellm.types.utils import CostPerToken
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_random_exponential,
)

from infant.config import LitellmParams
from infant.util.logger import infant_logger as logger
from infant.util.metrics import Metrics
from infant.agent.parser import parse
from infant.agent.memory.memory import Memory, Message


message_separator = '\n\n----------\n\n'
class LLM_API_BASED:
    """
    The LLM class represents a Language Model instance.

    Attributes:
        model_name (str): The name of the language model.
        api_key (str): The API key for accessing the language model.
        base_url (str): The base URL for the language model API.
        api_version (str): The version of the API to use.
        max_input_tokens (int): The maximum number of tokens to send to the LLM per task.
        max_output_tokens (int): The maximum number of tokens to receive from the LLM per task.
        llm_timeout (int): The maximum time to wait for a response in seconds.
        custom_llm_provider (str): A custom LLM provider.
    """

    def __init__(
        self,
        llm_config: LitellmParams
    ):
        """
        Initializes the LLM. If LLMConfig is passed, its values will be the fallback.

        Passing simple parameters always overrides config.

        Args:
            model (str, optional): The name of the language model. Defaults to LLM_MODEL.
            api_key (str, optional): The API key for accessing the language model. Defaults to LLM_API_KEY.
            base_url (str, optional): The base URL for the language model API. Defaults to LLM_BASE_URL. Not necessary for OpenAI.
            api_version (str, optional): The version of the API to use. Defaults to LLM_API_VERSION. Not necessary for OpenAI.
            num_retries (int, optional): The number of retries for API calls. Defaults to LLM_NUM_RETRIES.
            retry_min_wait (int, optional): The minimum time to wait between retries in seconds. Defaults to LLM_RETRY_MIN_TIME.
            retry_max_wait (int, optional): The maximum time to wait between retries in seconds. Defaults to LLM_RETRY_MAX_TIME.
            max_input_tokens (int, optional): The maximum number of tokens to send to the LLM per task. Defaults to LLM_MAX_INPUT_TOKENS.
            max_output_tokens (int, optional): The maximum number of tokens to receive from the LLM per task. Defaults to LLM_MAX_OUTPUT_TOKENS.
            custom_llm_provider (str, optional): A custom LLM provider. Defaults to LLM_CUSTOM_LLM_PROVIDER.
            llm_timeout (int, optional): The maximum time to wait for a response in seconds. Defaults to LLM_TIMEOUT.
            llm_temperature (float, optional): The temperature for LLM sampling. Defaults to LLM_TEMPERATURE.
            metrics (Metrics, optional): The metrics object to use. Defaults to None.
            cost_metric_supported (bool, optional): Whether the cost metric is supported. Defaults to True.
            feedback_mode (bool, optional): Whether the LLM is in feedback mode. Defaults to False.
        """
        logger.info(f'Initializing the api based LLM with the following parameters:')
        for attribute, value in llm_config.__dict__.items():
            logger.info(f"{attribute}: {value}")
        model = llm_config.model
        api_key = llm_config.api_key
        base_url = llm_config.base_url
        api_version = llm_config.api_version
        num_retries = llm_config.num_retries
        retry_min_wait = llm_config.retry_min_wait
        retry_max_wait = llm_config.retry_max_wait
        llm_timeout = llm_config.timeout
        llm_temperature = llm_config.temperature
        llm_top_p = llm_config.top_p
        custom_llm_provider = llm_config.custom_llm_provider
        max_input_tokens = llm_config.max_input_tokens
        max_output_tokens = llm_config.max_output_tokens
        metrics = Metrics()
        cost_metric_supported = llm_config.cost_metric_supported
        feedback_mode = llm_config.feedback_mode
        gift_key = llm_config.gift_key
        
        # Collect non-None parameters
        params = {
            'model': model,
            'api_key': api_key,
            'base_url': base_url,
            'api_version': api_version,
            'num_retries': num_retries,
            'retry_min_wait': retry_min_wait,
            'retry_max_wait': retry_max_wait,
            'llm_timeout': llm_timeout,
            'llm_temperature': llm_temperature,
            'llm_top_p': llm_top_p,
            'custom_llm_provider': custom_llm_provider,
            'max_input_tokens': max_input_tokens,
            'max_output_tokens': max_output_tokens,
            'cost_metric_supported': cost_metric_supported,
            'feedback_mode': feedback_mode
        }

        # Create a string of non-None parameters for logging
        non_none_str = ", ".join(f"{key}={value}" for key, value in params.items() if value is not None)
        logger.info(f'Initializing the Brain of the Agent with the following parameters: {non_none_str}')
        
        self.api_key = api_key
        self.gift_key = gift_key
        self.base_url = base_url
        self.model_name = model
        self.metrics = metrics
        self.llm_timeout = llm_timeout
        self.api_version = api_version
        self.feedback_mode = feedback_mode
        self.max_input_tokens = max_input_tokens
        self.max_output_tokens = max_output_tokens
        self.custom_llm_provider = custom_llm_provider
        self.cost_metric_supported = cost_metric_supported
        self.input_cost_per_token = llm_config.input_cost_per_token
        self.output_cost_per_token = llm_config.output_cost_per_token

        # litellm actually uses base Exception here for unknown model
        self.model_info = None
        try:
            if not self.model_name.startswith('openrouter'):
                self.model_info = litellm.get_model_info(self.model_name.split(':')[0])
            else:
                self.model_info = litellm.get_model_info(self.model_name)
        # noinspection PyBroadException
        except Exception:
            logger.warning(f'Could not get model info for {self.model_name}')

        if self.max_input_tokens is None:
            if self.model_info is not None and 'max_input_tokens' in self.model_info:
                self.max_input_tokens = self.model_info['max_input_tokens']
            else:
                # Max input tokens for gpt3.5, so this is a safe fallback for any potentially viable model
                self.max_input_tokens = 4096

        if self.max_output_tokens is None:
            if self.model_info is not None and 'max_output_tokens' in self.model_info:
                self.max_output_tokens = self.model_info['max_output_tokens']
            else:
                # Enough tokens for most output actions, and not too many for a bad llm to get carried away responding
                # with thousands of unwanted tokens
                self.max_output_tokens = 1024
        if self.gift_key:
            def call_llm(messages, max_tokens, top_p, temperature, stop):
                try:
                    from openai import OpenAI
                    client = OpenAI()
                    completion = client.chat.completions.create(
                        # model="anthropic.claude-3-5-sonnet-20241022-v2:0",
                        model = 'claude-3-7-sonnet-20250219',
                        messages=messages,
                        max_tokens=max_tokens,
                        top_p=top_p,
                        temperature=temperature,
                        stop=stop
                    )
                    return completion
                except Exception as e:
                    logger.error("Failed to call LLM: " + str(e))
                    return ""
            self._completion = partial(
                call_llm,
                max_tokens=self.max_output_tokens,
                top_p=llm_top_p,
                temperature=llm_temperature,
            )

        else:
            self._completion = partial(
                litellm_completion,
                model=self.model_name,
                api_key=self.api_key,
                base_url=self.base_url,
                api_version=self.api_version,
                custom_llm_provider=custom_llm_provider,
                max_tokens=self.max_output_tokens,
                timeout=self.llm_timeout,
                temperature=llm_temperature,
                top_p=llm_top_p,
            )

        completion_unwrapped = self._completion

        def attempt_on_error(retry_state):
            logger.error(
                f'{retry_state.outcome.exception()}. Attempt #{retry_state.attempt_number} | You can customize these settings in the configuration.',
                exc_info=False,
            )
            return True

        @retry(
            reraise=True,
            stop=stop_after_attempt(num_retries),
            wait=wait_random_exponential(min=retry_min_wait, max=retry_max_wait),
            retry=retry_if_exception_type(
                (RateLimitError, APIConnectionError, ServiceUnavailableError, 
                 InternalServerError, BadRequestError, APIError, OpenAIError)
            ),
            after=attempt_on_error,
        )
        def wrapper(*args, **kwargs):
            """
            Wrapper for the litellm completion function. Logs the input and output of the completion function.
            """

            # some callers might just send the messages directly
            if 'messages' in kwargs:
                messages = kwargs['messages']
            else:
                messages = args[1]

            # log the prompt
            debug_message = ''
            for message in messages:
                if isinstance(message['content'], str):
                    debug_message += message_separator + message['content']
                else: # image or other type
                    # assert litellm.supports_vision(model=self.model_name) == True # check if the model supports vision
                    debug_message += message_separator + 'message content is not a string!'

            ### For debugging only ###
            if 'messages' in kwargs:
                if isinstance(message['content'], str):
                    logger.debug("kwargs['messages'] contents:")
                    logger.debug(kwargs['messages'][-1]["role"].encode('utf-8').decode('unicode_escape', errors='replace'))
                    logger.debug(kwargs['messages'][-1]["content"].encode('utf-8').decode('unicode_escape', errors='replace'))
                else:
                    logger.debug('kwargs["messages"] content is not a string!')
            if feedback_mode:
                memory_block = []
                logger.debug(f'Feedback mode is enabled.')
                feedback = "None"
                while feedback != 'yes':
                    # call the completion function
                    resp = completion_unwrapped(*args, **kwargs)
                    assistant_response = resp['choices'][0]['message']['content']
                    print(f'Assistant response: \n{assistant_response}'.encode('utf-8').decode('unicode_escape', errors='replace'))
                    messages.append({
                        "role": "assistant",
                        "content": assistant_response
                    })
                    # post-process to log costs
                    self._post_completion(resp)
                    
                    messages, feedback, memory_block = self.human_feedback(messages, memory_block)
                    if feedback != 'yes':
                        memory_from_assistant = parse(assistant_response)
                        memory_block.insert(-1, memory_from_assistant)
                return resp['choices'][0]['message']['content'], memory_block
            else:
                if self.gift_key:
                    # call the completion function
                    resp = completion_unwrapped(*args, **kwargs)

                    # log the response
                    message_back = resp.choices[0].message.content
                    logger.debug(f'Assistant response: \n{message_back}'.encode('utf-8').decode('unicode_escape', errors='replace'))

                    # post-process to log costs
                    self._post_completion(resp)
                    return resp.choices[0].message.content, None                    
                else:
                    # call the completion function
                    resp = completion_unwrapped(*args, **kwargs)

                    # log the response
                    message_back = resp['choices'][0]['message']['content']
                    logger.debug(f'Assistant response: \n{message_back}'.encode('utf-8').decode('unicode_escape', errors='replace'))

                    # post-process to log costs
                    self._post_completion(resp)
                    return resp['choices'][0]['message']['content'], None

        self._completion = wrapper  # type: ignore

    @property
    def completion(self):
        """
        Decorator for the litellm completion function.

        Check the complete documentation at https://litellm.vercel.app/docs/completion
        """
        return self._completion

    def _post_completion(self, response: str) -> None:
        """
        Post-process the completion response.
        """
        try:
            cur_cost = self.completion_cost(response)
            caller = self._get_caller_function()
            if self.cost_metric_supported and cur_cost > 0:
                self.metrics.add_function_cost(caller, cur_cost)
                logger.info(
                    'Cost: %.6f USD | Accumulated Cost: %.6f USD',
                    cur_cost,
                    self.metrics.accumulated_cost,
                )
        except Exception as e:
            logger.warning(f"Error calculating cost: {e}")
            cur_cost = 0

    def get_token_count(self, messages):
        """
        Get the number of tokens in a list of messages.

        Args:
            messages (list): A list of messages.

        Returns:
            int: The number of tokens.
        """
        return litellm.token_counter(model=self.model_name, messages=messages)
    
    def human_feedback(self, messages: list, memory_block: list[Memory]):
        """
        Generates a response using the model and optionally collects feedback.
        
        Args:
            model: The model used to generate the response.
            input_data: Input data for the model.
            feedback_mode (bool): If True, enables manual feedback collection.
        
        Returns:
            response: The final model-generated response after feedback.
        """
        # Collect manual feedback
        feedback = input("Is the response correct? (yes/feedback): ").strip().lower()
        
        # Human feedback    
        if feedback != 'yes':
            messages.append({
                "role": "user",
                "content": feedback
            })
            memory_from_user = Message(content=feedback)
            memory_from_user.source = 'user'
            memory_block.append(memory_from_user)
            
        return messages, feedback, memory_block

    def is_local(self):
        """
        Determines if the system is using a locally running LLM.

        Returns:
            boolean: True if executing a local model.
        """
        if self.base_url is not None:
            for substring in ['localhost', '127.0.0.1' '0.0.0.0']:
                if substring in self.base_url:
                    return True
        elif self.model_name is not None:
            if self.model_name.startswith('ollama'):
                return True
        return False

    def completion_cost(self, response):
        """
        Calculate the cost of a completion response based on the model.  Local models are treated as free.
        Add the current cost into total cost in metrics.

        Args:
            response (list): A response from a model invocation.

        Returns:
            number: The cost of the response.
        """
        if not self.cost_metric_supported:
            return 0.0

        extra_kwargs = {}
        if (
            self.input_cost_per_token is not None
            and self.output_cost_per_token is not None
        ):
            cost_per_token = CostPerToken(
                input_cost_per_token=self.input_cost_per_token,
                output_cost_per_token=self.output_cost_per_token,
            )
            extra_kwargs['custom_cost_per_token'] = cost_per_token

        if not self.is_local():
            try:
                if self.gift_key:
                    input_tokens = response.usage.prompt_tokens
                    input_cost = input_tokens * self.input_cost_per_token
                    output_tokens = response.usage.completion_tokens
                    output_cost = output_tokens * self.output_cost_per_token
                    cost = input_cost + output_cost
                    self.metrics.add_cost(cost)
                else:
                    cost = litellm_completion_cost(
                        completion_response=response, **extra_kwargs
                    )
                    self.metrics.add_cost(cost)
                return cost
            except Exception:
                self.cost_metric_supported = False
                logger.warning('Cost calculation not supported for this model.')
        return 0.0

    def __str__(self):
        if self.api_version:
            return f'LLM(model={self.model_name}, api_version={self.api_version}, base_url={self.base_url})'
        elif self.base_url:
            return f'LLM(model={self.model_name}, base_url={self.base_url})'
        return f'LLM(model={self.model_name})'

    def __repr__(self):
        return str(self)

    def _get_caller_function(self) -> str:
        """
        Get the name of the calling function

        """
        frame = inspect.currentframe()
        try:
            while frame:
                if frame.f_code.co_name not in ['wrapper', '_get_caller_function', 'completion']:
                    return f"{frame.f_code.co_filename}:{frame.f_code.co_name}"
                frame = frame.f_back
            return "unknown"
        finally:
            del frame