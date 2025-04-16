from infant.helper_functions.browser_helper_function import *
from infant.helper_functions.visual_helper_functions import *

async def mouse_click(agent, memory, interactive_elements):
    '''
    Try three different methods to click on the interactive elements:
    1. Click on the element directly
    2. Write some js code
    3. Visual ability
    Input:
        agent: Agent
        memory: Memory
        interactive_elements: list
    Output:
        Updated memory
        Updated interactive_elements
    '''
    # prepare
    computer = agent.computer
    if isinstance(memory, IPythonRun) and memory.code:
        pattern = r"mouse_(?:left_click|double_click|move|right_click)\(.*?\)"
        match = re.search(pattern, memory.code)
        if match:
            logger.info(f"=========Start Browser localization=========")
            icon, desc = extract_icon_and_desc(memory.code)
            if icon is None or desc is None:
                logger.info(f"=========End Browser localization=========")
                return memory, interactive_elements
            logger.info(f"Icon: {icon}, Desc: {desc}")
            get_state_action = IPythonRun(code=GET_STATE_CODE)
            browser_state = await computer.run_ipython(get_state_action)
            remove_highlight_action = IPythonRun(code='await context.remove_highlights()')
            await computer.run_ipython(remove_highlight_action)
            
            # Click on the element directly
            element_index = await image_description_to_element_index(agent, computer, icon, 
                                                                     desc, browser_state)
            logger.info(f"Element Index: {element_index}")            
            if isinstance(element_index, int):
                interactive_elements.append(element_index)
                try_code = replace_icon_desc_with_element_index(memory.code, element_index) # replace the image description with the element index
                
                # Try to click
                try_code = f'await context.{try_code}\ntake_screenshot()'
                try_memory = IPythonRun(code=try_code)
                try_result = await computer.run_ipython(try_memory)
                if not 'Traceback (most recent call last)' in try_result:   
                    logger.info(f"Mouse clicked at Element Index: ({element_index})")                    
                    logger.info(f"=========End Browser localization=========")
                    memory.result = try_result
                    return memory, interactive_elements
                else:
                    logger.info(f"Mouse click failed at Element Index: ({element_index})")
            
            # # Write some js code
            # logger.info("Element Index is not a valid int. Trying to use js code")
            # # try to use execute the javascript to simulate the click
            # try_code = await image_description_to_executable_js(agent, computer, icon, 
            #                                                             desc, browser_state)
            # if try_code is not None:
            #     try_code = '(function() {\n' + try_code + '\n})();'
            #     try_code = json.dumps(try_code)
            #     # Try to run the js code
            #     try_code = f'await context.execute_javascript({try_code})\ntake_screenshot()'
            #     try_memory = IPythonRun(code=try_code)
            #     try_result = await computer.run_ipython(try_memory)
            #     if not 'Traceback (most recent call last)' in try_result:   
            #         logger.info(f"Finish executing js code: ({try_code})")                    
            #         logger.info(f"=========End Browser localization=========")
            #         memory.result = try_result
            #         return memory, interactive_elements
            #     else:
            #         logger.info(f"Mouse click failed to run js code: ({try_code})")
                
            # Visual ability
            memory = await localization_visual(agent, memory)
    return memory, interactive_elements