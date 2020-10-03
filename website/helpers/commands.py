from types import MethodType
from helpers.patterns import Register
from helpers.utilities import to_snake_case


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

    @property
    def name(self):
        return to_snake_case(self.__class__.__name__)

    def get_methods(self):
        return [
            (name, getattr(self, name))
            for name in dir(self)
            if isinstance(getattr(self, name), MethodType)
        ]

    def get_arguments(self, command_func):

        return [
            value()
            for key, value in self.get_methods()
            if (
                value and value.__dict__.get('is_argument', False) and
                (
                    (value.__dict__.get('commands') == 'all') or
                    (command_func in value.__dict__.get('commands'))
                )
            )
        ]

    def supports(self, command_name):
        members = dict(self.get_methods())
        function = members.get(command_name, None)
        return function and function.__dict__.get('is_command', False)


def create_command_subparsers(command_parsers, **top_kwargs):
    handlers = [
        command_target()
        for command_target in CommandTarget
    ]
    for command, command_parser in command_parsers.items():
        subparsers = command_parser.add_subparsers(help='sub-commands')

        for handler in handlers:
            if handler.supports(command):

                subparser = subparsers.add_parser(
                    handler.name,
                    help=handler.description.format(command=command),
                    **top_kwargs
                )
                command_func = getattr(handler, command)
                subparser.set_defaults(func=command_func)

                for arg_parameters in handler.get_arguments(command_func.__func__):
                    args, kwargs = arg_parameters
                    subparser.add_argument(*args, **kwargs)


def get_answer(question, choices={'y': True, 'n': False}):
    choices = {str(code): value for code, value in choices.items()}
    while True:
        answer = input(f'\n{question} ({"/".join(choices)})? ')
        if answer in choices:
            return choices[answer]


got_permission = get_answer
