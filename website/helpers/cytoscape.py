import json
from copy import copy
from types import SimpleNamespace
from urllib.parse import urlencode
from warnings import warn
from time import sleep

import requests


class Namespace(SimpleNamespace):

    def __init__(self, data):
        super().__init__(**data)


class Endpoint:

    def __init__(self, method, defaults=None, python_type=dict, content_type='application/json', name=None):
        self.method = method
        self.defaults = defaults or {}
        self.python_type = python_type
        self.content_type = content_type
        self.name = name


def method_factory(method_name):

    def method(plain_text=False, **kwargs):
        if plain_text:
            return Endpoint(method_name, content_type='text/plain', python_type=str, **kwargs)
        return Endpoint(method_name, **kwargs)

    method.__name__ = method_name

    return method


get = method_factory('get')
post = method_factory('post')


class EndpointsBinder(type):

    def __new__(mcs, class_name, bases, new_attrs):

        for name, attr in new_attrs.items():
            if isinstance(attr, Endpoint):

                def endpoint(self, _attr=attr, _name=name, **kwargs):
                    all_kwargs = copy(_attr.defaults)
                    all_kwargs.update(kwargs)
                    if _attr.name is not None:
                        _name = _attr.name
                    return self.send_and_receive(_attr, _name, **all_kwargs)

                new_attrs[name] = endpoint

        return super().__new__(mcs, class_name, bases, new_attrs)


class JSONPythonRestAPI(metaclass=EndpointsBinder):

    def __init__(self, url):
        self.url = url

    def send_and_receive(self, endpoint, name, data=None, **kwargs):

        if endpoint.method == 'post':
            assert not kwargs
        elif data:
            kwargs['data'] = data

        send = getattr(requests, endpoint.method)

        url = f'{self.url}'
        if name:
            url += f'/{name}'
        if kwargs:
            url += '?' + urlencode(kwargs)

        response = send(
            url,
            data=json.dumps(data),
            headers={'Content-Type': endpoint.content_type}
        )

        try:
            if endpoint.content_type == 'application/json':
                return endpoint.python_type(response.json())
            else:
                return endpoint.python_type(response.text)
        except ValueError:
            warn(f'Cannot decode {url} response: {response.text}')
            raise


class CytoscapeAPI(JSONPythonRestAPI):

    def __init__(self, url='http://localhost', port=1234, version=1):

        super().__init__(f'{url}:{port}/v{version}')


class CytoscapeCommand(CytoscapeAPI):

    def __init__(self, *args, name=None, **kwargs):
        super().__init__(*args, **kwargs)

        if not name:
            name = self.__class__.__name__.lower()

        self.url += f'/commands/{name}'


class Session(CytoscapeCommand):

    save_as = post(name='save as')
    new = post(defaults={'data': {}})


class Cytoscape(CytoscapeAPI):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.session = Session(*args, **kwargs)

        is_server_ready = False
        # wait for REST server to load
        while not is_server_ready:
            try:
                status = self.get_status()
                if status:
                    print('Connected to server', status.apiVersion)
                    is_server_ready = True
            except (IOError, ValueError):
                pass
            sleep(1)

    get_status = get(name='', python_type=Namespace)
