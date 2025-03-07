def print_messages(dc_messages, function_name):
    def format_message_content(message):
        content = message.get("content", '')
        if isinstance(content, str):
            return content
        if isinstance(content, list) and content and isinstance(content[0], dict) and "text" in content[0]:
            return content[0]["text"] + " <image>"
        return "<image>"

    printable_messages = [
        {
            "role": message["role"],
            "content": format_message_content(message)
        }
        for message in dc_messages
    ]

    print(f'Messages in {function_name}: {printable_messages}')