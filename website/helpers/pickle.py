import codecs
import pickle


def pickle_as_str(obj):
    return codecs.encode(pickle.dumps(obj, protocol=0), 'base64').decode()


def unpickle_str(text):
    return pickle.loads(codecs.decode(text.encode(), 'base64'))
