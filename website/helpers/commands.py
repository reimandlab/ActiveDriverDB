from types import FunctionType
from helpers.patterns import Register


def register_decorator(register):
    def decorator(func):
        register[func.__name__] = func
        return func
    return decorator


def argument_parameters(*args, **kwargs):
    return args, kwargs


def command(func):
    method = func
    method.is_command = True
    func.argument = command_argument(method)
    return method


def command_argument(command_func):
    def argument_closure(func):
        func.commands = [command_func]
        func.is_argument = True
        return func
    return argument_closure


def argument(func):
    func.is_argument = True
    func.commands = 'all'
    return func


class CommandTarget(metaclass=Register):

    @classmethod
    def name(cls):
        camel_name = cls.__name__
        underscore_name = ''
        was_up = True
        for c in camel_name:
            is_up = c.isupper()
            if is_up and not was_up:
                underscore_name += '_'
            was_up = is_up
            underscore_name += c.lower()
        return underscore_name

    @classmethod
    def get_methods(cls):
        return [
            (name, getattr(cls, name))
            for name in dir(cls)
            if isinstance(getattr(cls, name), FunctionType)
        ]

    @classmethod
    def get_arguments(cls, command_func):
        return [
            value()
            for key, value in cls.get_methods()
            if (
                value and value.__dict__.get('is_argument', False) and
                (
                    (value.__dict__.get('commands') == 'all') or
                    (command_func in value.__dict__.get('commands'))
                )
            )
        ]

    @classmethod
    def supports(cls, command_name):
        members = dict(cls.get_methods())
        function = members.get(command_name, None)
        return function and function.__dict__.get('is_command', False)


def create_command_subparsers(command_parsers):
    for command, command_parser in command_parsers.items():
        subparsers = command_parser.add_subparsers(help='sub-commands')

        for handler in CommandTarget:
            if handler.supports(command):

                subparser = subparsers.add_parser(
                    handler.name(),
                    help=handler.description.format(command=command)
                )
                command_func = getattr(handler, command)
                subparser.set_defaults(func=command_func)

                for arg_parameters in handler.get_arguments(command_func):
                    args, kwargs = arg_parameters
                    subparser.add_argument(*args, **kwargs)
