def camel_to_snake(camel_str):
    s = ''
    if camel_str[0].isupper():
        camel_str = camel_str[0].lower() + camel_str[1:]
    for c in camel_str:
        if c.isupper():
            s += '_' + c.lower()
        else:
            s += c
    return s


def snake_to_camel(snake_str):
    camel = ''
    snake_str = snake_str[0].upper() + snake_str[1:]
    to_upper = False
    for s in snake_str:
        if s == '_':
            to_upper = True
        elif to_upper is True:
            camel += s.upper()
            to_upper = False
        else:
            camel += s
    return camel
