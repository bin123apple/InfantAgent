import logging
import os
import pathlib
import platform
import uuid
from dataclasses import dataclass
from typing import Optional, Union, List
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

load_dotenv() # FIXME: Access api-key from environment variable

@dataclass
class Config:
    """
    ### litellm Attributes: # for LLM ###
    model: The model to use.
    api_key: The API key to use.
    base_url: The base URL for the API. This is necessary for local LLMs. It is also used for Azure embeddings.
    api_version: The version of the API.
    embedding_model: The embedding model to use.
    embedding_base_url: The base URL for the embedding API.
    embedding_deployment_name: The name of the deployment for the embedding API. This is used for Azure OpenAI.
    aws_access_key_id: The AWS access key ID.
    aws_secret_access_key: The AWS secret access key.
    aws_region_name: The AWS region name.
    num_retries: The number of retries to attempt.
    retry_min_wait: The minimum time to wait between retries, in seconds. This is exponential backoff minimum. For models with very low limits, this can be set to 15-20.
    retry_max_wait: The maximum time to wait between retries, in seconds. This is exponential backoff maximum.
    timeout: The timeout for the API.
    max_chars: The maximum number of characters to send to and receive from the API. This is a fallback for token counting, which doesn't work in all cases.
    temperature: The temperature for the API.
    top_p: The top p for the API.
    custom_llm_provider: The custom LLM provider to use. It is documented on the litellm side.
    max_input_tokens: The maximum number of input tokens. Note that this is currently unused, and the value at runtime is actually the total tokens in OpenAI (e.g. 128,000 tokens for GPT-4).
    max_output_tokens: The maximum number of output tokens. This is sent to the LLM.
    input_cost_per_token: The cost per input token. This will available in logs for the user to check.
    output_cost_per_token: The cost per output token. This will available in logs for the user to check.
    
    
    ### vllm Attributes: # for OSS-LLM inference ###
    model_name: The name of the model to use.
    tensor_parallel_size: The size of the tensor parallelism.
    max_model_len: The maximum length of the model.
    disable_custom_all_reduce: Whether to disable custom all-reduce operations.
    enable_prefix_caching: Whether to enable prefix caching.
    trust_remote_code: Whether to trust remote code execution for model loading.
    sampling_n: Number of samples to generate per request.
    max_tokens: Maximum number of tokens to generate.
    vllm_temperature: Sampling temperature for randomness in generation.
    sampling_top_p: Top-p sampling threshold.
    stop: Stop tokens for text generation.    
    
    
    ### agent Attributes: # for agent ###
    run_as_infant: Whether to run as AI.
    max_iterations: The maximum number of iterations.
    max_voting: The maximum number of voting iterations.
    max_budget_per_task: The maximum budget allowed per task, beyond which the agent will stop.
    max_planning_iterations: max number of retries for basic tasks
    max_execution_iterations: max number of retries for evaluation tasks
    max_self_modify_basic: max number of self-modifications allowed (code linting, etc.)
    max_critic_retries: max number of retries for critic
    max_action_times: max number of actions in one basic_retry
    max_finish_retry: max number of retries before the agent finishes the task
    max_chars: The maximum number of characters to send to and receive from LLM per task.
    max_message_retry: max number of retries for message actions (e.g. message actions appear in the middle of the analysis)
    max_continuous_errors: max number of continuous errors before the agent stops
    use_oss_llm: whether to use API for hands
    debug: Whether to enable debugging.
    enable_auto_lint: Whether to enable auto linting. This is False by default, for regular runs of the app. For evaluation, please set this to True.
    
    ### Computer Attributes: # for computer ###
    runtime: The runtime environment.
    file_store: The file store to use.
    file_store_path: The path to the file store.
    workspace_base: The base path for the workspace. Defaults to ./workspace as an absolute path.
    workspace_mount_path: The path to mount the workspace. This is set to the workspace base by default.
    workspace_mount_path_in_computer: The path to mount the workspace in the computer. Defaults to /workspace.
    workspace_mount_rewrite: The path to rewrite the workspace mount path to.
    cache_dir: The path to the cache directory. Defaults to /tmp/cache.
    computer_container_image: The container image to use for the computer.
    computer_type: The type of computer to use. Options are: ssh, exec, e2b, local.
    use_host_network: Whether to use the host network.
    ssh_hostname: The SSH hostname.
    disable_color: Whether to disable color. For terminals that don't support color.
    computer_user_id: The user ID for the computer.
    computer_timeout: The timeout for the computer.
    """
    
    # litellm Attributes
    model: str = 'claude-3-7-sonnet-latest'
    api_key: str | None = os.getenv("ANTHROPIC_API_KEY")
    # model: str = 'o4-mini'
    # api_key: str | None = os.getenv("OPENAI_API_KEY")
    base_url: str | None = None
    api_version: str | None = None
    embedding_model: str = 'local'
    embedding_base_url: str | None = None
    embedding_deployment_name: str | None = None
    aws_access_key_id: str | None = None
    aws_secret_access_key: str | None = None
    aws_region_name: str | None = None
    num_retries: int = 5
    retry_min_wait: int = 5
    retry_max_wait: int = 60
    timeout: int | None = None
    max_chars: int = 5_000_000  # fallback for token counting
    temperature: float = 0.9
    top_p: float = 0.5
    custom_llm_provider: str | None = None
    max_input_tokens: int | None = None
    max_output_tokens: int | None = 8191
    input_cost_per_token: float | None = 0.000003
    output_cost_per_token: float | None = 0.000015
    cost_metric_supported: bool = True
    feedback_mode: bool = False
    gift_key: bool = False
    
    ## vllm Attributes
    model_name: str = 'weitaikang/RL-Qwen2.5VL-lora-7B-ckpt500'
    tensor_parallel_size: int = 2 # Tensor parallelism splits the model's tensors across n GPUs
    max_model_len: int = 9632
    disable_custom_all_reduce: bool = True
    enable_prefix_caching: bool = False
    trust_remote_code: bool = True
    gpu_memory_utilization: float = 0.7 # kv cache memory utilization
    sampling_n: int = 1
    best_of: Optional[int] = None
    presence_penalty: float = 0.0
    frequency_penalty: float = 0.0
    repetition_penalty: float = 1.0
    vllm_temperature: float = 0
    vllm_top_p: float = 1.0
    vllm_top_k: int = -1
    min_p: float = 0.0
    seed: Optional[int] = None
    use_beam_search: bool = False
    length_penalty: float = 1.0
    early_stopping: Union[bool, str] = False
    stop: Optional[Union[str, List[str]]] = None
    stop_token_ids: Optional[List[int]] = None
    ignore_eos: bool = False
    max_tokens: Optional[int] = 9632
    min_tokens: int = 0
    max_retries: int = 10
    
    # agent Attributes
    run_as_infant: bool = True # whether to run as AI, if use login as root, some application may not work, such as chrome
    max_iterations: int = 100
    max_voting: int = 5
    max_sum_retries: int = 3
    max_budget_per_task: float | None = 4
    max_planning_iterations: int = 5 # max number of retries for planning
    max_execution_iterations: int = 10 # max number of retries for execution
    max_self_modify_basic: int = 20 # max number of self-modifications allowed (code linting, etc.)
    max_self_modify_advanced: int = 7
    max_critic_retries: int = 0 # max number of retries for critic
    max_action_times = 30 # max number of actions in one basic_retry
    max_finish_retry = 3 # max number of retries before the agent finishes the task
    max_message_retry = 3 # max number of retries for message actions (e.g. message actions appear in the middle of the analysis)
    max_continuous_errors = 10 # max number of continuous errors before the agent stops
    use_oss_llm = True # whether to use OSS LLM (Need GPU!)
    verify_step_by_step: bool = True
    fake_response_mode: bool = False
    
    # Computer Attributes 
    runtime: str = 'server'
    file_store: str = 'memory'
    file_store_path: str = '/tmp/file_store'
    instance_id: str = '123'
    gui_port: str = '4443'
    workspace_git_path: str = '/workspace' # The path to the git repo in the computer
    workspace_base: str = os.path.join(os.getcwd(), 'workspace')
    workspace_mount_path: str = 'undefined'
    workspace_mount_path_in_computer: str = '/workspace'
    workspace_mount_rewrite: str | None = None
    cache_dir: str = '/tmp/cache'
    computer_container_image: str = 'ubuntu-gnome-nomachine:22.04' # FIXME: change to a general image name    
    e2b_api_key: str = ''
    computer_type: str = 'ssh'  # Can be 'ssh', 'exec', or 'e2b'
    use_host_network: bool = False
    ssh_hostname: str = 'localhost'
    disable_color: bool = False
    computer_user_id: int = os.getuid() if hasattr(os, 'getuid') else 1000
    computer_timeout: int = 120
    initialize_plugins: bool = True
    ssh_port: int = 63710
    ssh_password: str | None = "123"
    jwt_secret: str = uuid.uuid4().hex
    debug: bool = False  
    enable_auto_lint: bool = True  
    nvidia_driver: str = 'Tesla'
    render_type: str = 'Gpu' # Use CPU or GPU for rendering
    nvidia_visible_devices: str = '0'
    ssh_bind_port: int = 22222
    nomachine_bind_port: int = 23333
    consistant_computer: bool = True # whether to use the same computer for the same user
    text_only_docker: bool = False # whether to use a text-only docker image
    intermediate_results_dir: str = os.path.join(os.getcwd(), 'workspace')
    
    def __str__(self):
        sections = [
            ("### litellm Attributes ###", self.get_litellm_params()),
            ("### vllm Attributes ###", self.get_vllm_params()),
            ("### agent Attributes ###", self.get_agent_params()),
            ("### Computer Attributes ###", self.get_computer_params()),
        ]

        # Format each section
        return '\n\n'.join([f"{title}\n" + '\n'.join([f"{key}: {value}" for key, value in params.items()]) for title, params in sections])


    def finalize_config(self):
        """
        More tweaks to the config after it's been loaded.
        """

        # Set workspace_mount_path if not set by the user
        if self.workspace_mount_path == 'undefined':
            self.workspace_mount_path = os.path.abspath(self.workspace_base)
        self.workspace_base = os.path.abspath(self.workspace_base)

        # In local there is no computer, the workspace will have the same pwd as the host
        if self.computer_type == 'local':
            self.workspace_mount_path_in_computer = self.workspace_mount_path

        if self.workspace_mount_rewrite: 
            base = self.workspace_base or os.getcwd()
            parts = self.workspace_mount_rewrite.split(':')
            self.workspace_mount_path = base.replace(parts[0], parts[1])

        if self.embedding_base_url is None:
            self.embedding_base_url = self.base_url

        if self.use_host_network and platform.system() == 'Darwin':
            logger.warning(
                'Please upgrade to Docker Desktop 4.29.0 or later to use host network mode on macOS. '
                'See https://github.com/docker/roadmap/issues/238#issuecomment-2044688144 for more information.'
            )

        # make sure cache dir exists
        if self.cache_dir:
            pathlib.Path(self.cache_dir).mkdir(parents=True, exist_ok=True)
            
            
    def get_litellm_params(self):
        return LitellmParams(
            model=self.model,
            api_key=self.api_key,
            base_url=self.base_url,
            api_version=self.api_version,
            embedding_model=self.embedding_model,
            embedding_base_url=self.embedding_base_url,
            embedding_deployment_name=self.embedding_deployment_name,
            aws_access_key_id=self.aws_access_key_id,
            aws_secret_access_key=self.aws_secret_access_key,
            aws_region_name=self.aws_region_name,
            num_retries=self.num_retries,
            retry_min_wait=self.retry_min_wait,
            retry_max_wait=self.retry_max_wait,
            timeout=self.timeout,
            max_chars=self.max_chars,
            temperature=self.temperature,
            top_p=self.top_p,
            cost_metric_supported = self.cost_metric_supported,
            custom_llm_provider=self.custom_llm_provider,
            max_input_tokens=self.max_input_tokens,
            max_output_tokens=self.max_output_tokens,
            input_cost_per_token=self.input_cost_per_token,
            output_cost_per_token=self.output_cost_per_token,
            feedback_mode = self.feedback_mode,
            gift_key=self.gift_key
        )

    def get_vllm_params(self):
        return VllmParams(
            model_name=self.model_name,
            tensor_parallel_size=self.tensor_parallel_size,
            max_model_len=self.max_model_len,
            disable_custom_all_reduce=self.disable_custom_all_reduce,
            enable_prefix_caching=self.enable_prefix_caching,
            trust_remote_code=self.trust_remote_code,
            sampling_n=self.sampling_n,
            max_tokens=self.max_tokens,
            vllm_temperature=self.vllm_temperature,
            vllm_top_p=self.vllm_top_p,
            stop=self.stop,
            gpu_memory_utilization=self.gpu_memory_utilization
        )

    def get_agent_params(self):
        return AgentParams(
            max_iterations=self.max_iterations,
            max_voting=self.max_voting,
            max_budget_per_task=self.max_budget_per_task,
            max_planning_iterations=self.max_planning_iterations,
            max_execution_iterations=self.max_execution_iterations,
            max_self_modify_basic=self.max_self_modify_basic,
            max_self_modify_advanced=self.max_self_modify_advanced,
            max_critic_retries=self.max_critic_retries,
            max_action_times=self.max_action_times,
            max_finish_retry=self.max_finish_retry,
            max_message_retry=self.max_message_retry,
            max_sum_retries = self.max_sum_retries,
            max_continuous_errors=self.max_continuous_errors,
            use_oss_llm=self.use_oss_llm,
            debug=self.debug,
            fake_response_mode = self.fake_response_mode
        )
    
    def get_computer_params(self):
        return ComputerParams(
            runtime=self.runtime,
            file_store=self.file_store,
            file_store_path=self.file_store_path,
            instance_id=self.instance_id,
            gui_port = self.gui_port,
            workspace_git_path = self.workspace_git_path,
            workspace_base=self.workspace_base,
            workspace_mount_path=self.workspace_mount_path,
            workspace_mount_path_in_computer=self.workspace_mount_path_in_computer,
            workspace_mount_rewrite=self.workspace_mount_rewrite,
            cache_dir=self.cache_dir,
            computer_container_image=self.computer_container_image,
            computer_type=self.computer_type,
            use_host_network=self.use_host_network,
            ssh_hostname=self.ssh_hostname,
            disable_color=self.disable_color,
            computer_user_id=self.computer_user_id,
            computer_timeout=self.computer_timeout,
            enable_auto_lint=self.enable_auto_lint,
            run_as_infant=self.run_as_infant,
            ssh_password = self.ssh_password,
            initialize_plugins = self.initialize_plugins,
            render_type = self.render_type,
            nvidia_driver = self.nvidia_driver,
            nvidia_visible_devices = self.nvidia_visible_devices,
            ssh_bind_port = self.ssh_port,
            nomachine_bind_port = self.nomachine_bind_port,
            consistant_computer = self.consistant_computer,
            text_only_docker = self.text_only_docker,
            intermediate_results_dir = self.intermediate_results_dir
        )

class ComputerParams:
    def __init__(
        self,
        runtime,
        file_store,
        file_store_path,
        instance_id,
        gui_port,
        text_only_docker,
        workspace_git_path,
        workspace_base,
        workspace_mount_path,
        workspace_mount_path_in_computer,
        workspace_mount_rewrite,
        cache_dir,
        computer_container_image,
        computer_type,
        use_host_network,
        ssh_hostname,
        disable_color,
        computer_user_id,
        computer_timeout,
        enable_auto_lint,
        run_as_infant,
        ssh_password,
        initialize_plugins,
        nvidia_driver,
        render_type,
        nvidia_visible_devices,
        ssh_bind_port,
        nomachine_bind_port,
        consistant_computer,
        intermediate_results_dir
    ):
        self.runtime = runtime
        self.file_store = file_store
        self.file_store_path = file_store_path
        self.instance_id = instance_id
        self.gui_port = gui_port
        self.workspace_git_path = workspace_git_path
        self.workspace_base = workspace_base
        self.text_only_docker = text_only_docker
        self.workspace_mount_path = workspace_mount_path
        self.workspace_mount_path_in_computer = workspace_mount_path_in_computer
        self.workspace_mount_rewrite = workspace_mount_rewrite
        self.cache_dir = cache_dir
        self.computer_container_image = computer_container_image
        self.computer_type = computer_type
        self.use_host_network = use_host_network
        self.ssh_hostname = ssh_hostname
        self.disable_color = disable_color
        self.computer_user_id = computer_user_id
        self.computer_timeout = computer_timeout
        self.enable_auto_lint = enable_auto_lint
        self.run_as_infant = run_as_infant
        self.ssh_password = ssh_password
        self.initialize_plugins = initialize_plugins
        self.nvidia_driver = nvidia_driver
        self.render_type = render_type
        self.nvidia_visible_devices = nvidia_visible_devices
        self.ssh_bind_port = ssh_bind_port
        self.nomachine_bind_port = nomachine_bind_port
        self.consistant_computer = consistant_computer
        self.intermediate_results_dir = intermediate_results_dir

class LitellmParams:
    def __init__(
        self,
        model,
        api_key,
        base_url,
        gift_key,
        api_version,
        embedding_model,
        embedding_base_url,
        embedding_deployment_name,
        aws_access_key_id,
        aws_secret_access_key,
        aws_region_name,
        num_retries,
        retry_min_wait,
        retry_max_wait,
        timeout,
        max_chars,
        temperature,
        top_p,
        custom_llm_provider,
        max_input_tokens,
        max_output_tokens,
        input_cost_per_token,
        output_cost_per_token,
        cost_metric_supported,
        feedback_mode,
    ):
        self.model = model
        self.api_key = api_key
        self.base_url = base_url
        self.gift_key = gift_key
        self.api_version = api_version
        self.embedding_model = embedding_model
        self.embedding_base_url = embedding_base_url
        self.embedding_deployment_name = embedding_deployment_name
        self.aws_access_key_id = aws_access_key_id
        self.aws_secret_access_key = aws_secret_access_key
        self.aws_region_name = aws_region_name
        self.num_retries = num_retries
        self.retry_min_wait = retry_min_wait
        self.retry_max_wait = retry_max_wait
        self.timeout = timeout
        self.max_chars = max_chars
        self.temperature = temperature
        self.top_p = top_p
        self.cost_metric_supported = cost_metric_supported
        self.custom_llm_provider = custom_llm_provider
        self.max_input_tokens = max_input_tokens
        self.max_output_tokens = max_output_tokens
        self.input_cost_per_token = input_cost_per_token
        self.output_cost_per_token = output_cost_per_token
        self.feedback_mode = feedback_mode
        
class VllmParams:
    def __init__(
        self,
        model_name,
        tensor_parallel_size,
        max_model_len,
        disable_custom_all_reduce,
        enable_prefix_caching,
        trust_remote_code,
        sampling_n,
        max_tokens,
        vllm_temperature,
        vllm_top_p,
        stop,
        gpu_memory_utilization,
    ):
        self.model_name = model_name
        self.tensor_parallel_size = tensor_parallel_size
        self.max_model_len = max_model_len
        self.disable_custom_all_reduce = disable_custom_all_reduce
        self.enable_prefix_caching = enable_prefix_caching
        self.trust_remote_code = trust_remote_code
        self.sampling_n = sampling_n
        self.max_tokens = max_tokens
        self.vllm_temperature = vllm_temperature
        self.vllm_top_p = vllm_top_p
        self.stop = stop     
        self.gpu_memory_utilization = gpu_memory_utilization   

class AgentParams:
    def __init__(
        self,
        max_iterations,
        max_voting,
        max_budget_per_task,
        max_planning_iterations,
        max_execution_iterations,
        max_sum_retries,
        max_self_modify_basic,
        max_self_modify_advanced,
        max_critic_retries,
        max_action_times,
        max_finish_retry,
        max_message_retry,
        max_continuous_errors,
        use_oss_llm,
        debug,
        fake_response_mode,
    ):
        self.max_iterations = max_iterations
        self.max_voting = max_voting
        self.max_budget_per_task = max_budget_per_task
        self.max_planning_iterations = max_planning_iterations
        self.max_execution_iterations = max_execution_iterations
        self.max_sum_retries = max_sum_retries
        self.max_self_modify_basic = max_self_modify_basic
        self.max_self_modify_advanced = max_self_modify_advanced
        self.max_critic_retries = max_critic_retries
        self.max_action_times = max_action_times
        self.max_finish_retry = max_finish_retry
        self.max_message_retry = max_message_retry
        self.max_continuous_errors = max_continuous_errors
        self.use_oss_llm = use_oss_llm
        self.debug = debug
        self.fake_response_mode = fake_response_mode
        
config = Config()
config.finalize_config()
