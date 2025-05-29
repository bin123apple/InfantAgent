localization_prompt = '''I want to click on {item_to_click} with the mouse. 
Please help me determine the exact coordinates I need to click on. 
I will provide you with a screenshot of my computer screen, divided into sections with dashed lines, and coordinates labeled at each intersection point. 
If you need to zoom in on the screen for more precise coordinate identification, please use the following function:
localization(top_left: tuple | None = None, length: int | None = None)
This function is used to zoom in on the screen by specifying the top-left corner and the length of the zoomed-in area.
Args:
    top_left (tuple | None): 
        The top-left corner of the screenshot region as a tuple of (x, y) coordinates. 
        If None, the screenshot will cover the entire screen. Defaults to None.
    
    length (int | None): 
        The side length of the screenshot region, forming a square. 
        If None, the screenshot region will cover the entire screen or be determined dynamically. Defaults to None.
You only need to generate the function itself and place it within the <execute_ipython>...</execute_ipython> tags.
For example:
User:
I want to click on {item_to_click} with the mouse. Please help me determine its **EXACT** coordinates.

Assistant:
<execute_ipython>localization(top_left = (200, 600), length = 400)</execute_ipython>

User:
Screenshot Figure

Assistant:
<execute_ipython>localization(top_left = (400, 700), length = 200)</execute_ipython>

User:
Screenshot Figure

Assistant:
The coordinates are (530,710).:
<loca_finish>(530,710)</loca_finish>

Now, let's work on the real task:
'''

localization_user_initial_prompt = '''I want to click on {item_to_click} with the mouse. {Location} Please help me determine its **EXACT** coordinates.
You can use localization() function to zoom in on the screen for more precise coordinate identification.'''

localization_fake_user_response_prompt = '''Please give me a command.'''

localization_check_dot_prompt = '''I have marked the location you selected with a red dot in the image. 
Please confirm whether the location you selected is correct. If it is incorrect, you can use the command <loca_finish>coordination</loca_finish> to reselect the coordinates or <execute_ipython>localization()</execute_ipython> to choose another area. 
If you believe the location you selected is correct, please respond with <|exit|>.'''

localization_check_rectangle_prompt = '''I have marked the area you selected with a red dot in the image. 
Please confirm whether the area you selected is correct. If it is incorrect, you can use the command <execute_ipython>localization()</execute_ipython> to select another area. 
If you believe the area you selected is correct, please respond with <|exit|>.'''