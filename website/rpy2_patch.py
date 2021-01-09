import os
import typing
from rpy2.rinterface_lib import openrlib
from rpy2.rinterface_lib import callbacks
from rpy2.rinterface_lib.embedded import setinitialized, CALLBACK_INIT_PAIRS, _setcallback, isinitialized

ffi = openrlib.ffi

_options = ('rpy2', '--quiet', '--no-save')  # type: typing.Tuple[str, ...]
_DEFAULT_C_STACK_LIMIT = -1
rpy2_embeddedR_isinitialized = 0x00


def _initr(
        interactive: bool = True,
        _want_setcallbacks: bool = True,
        _c_stack_limit: int = _DEFAULT_C_STACK_LIMIT
) -> typing.Optional[int]:

    rlib = openrlib.rlib
    ffi_proxy = openrlib.ffi_proxy
    if (
            ffi_proxy.get_ffi_mode(openrlib._rinterface_cffi)
            ==
            ffi_proxy.InterfaceType.ABI
    ):
        callback_funcs = callbacks
    else:
        callback_funcs = rlib

    with openrlib.rlock:
        if isinitialized():
            return None
        if openrlib.R_HOME is None:
            raise ValueError('openrlib.R_HOME cannot be None.')
        os.environ['R_HOME'] = openrlib.R_HOME
        options_c = [ffi.new('char[]', o.encode('ASCII')) for o in _options]
        n_options = len(options_c)
        n_options_c = ffi.cast('int', n_options)
        rlib.Rf_initialize_R(n_options_c, options_c)

        if _c_stack_limit:
            rlib.R_CStackLimit = ffi.cast('uintptr_t', _c_stack_limit)

        rlib.setup_Rmainloop()
        setinitialized()

        # global rstart
        # rstart = ffi.new('Rstart')

        rlib.R_Interactive = interactive

        # TODO: Conditional definition in C code
        #   (Aqua, TERM, and TERM not "dumb")
        rlib.R_Outputfile = ffi.NULL
        rlib.R_Consolefile = ffi.NULL

        # TODO: Conditional in C code
        rlib.R_SignalHandlers = 0

        if _want_setcallbacks:
            for rlib_symbol, callback_symbol in CALLBACK_INIT_PAIRS:
                _setcallback(rlib, rlib_symbol,
                             callback_funcs, callback_symbol)

        # TODO: still needed ?

        return 1
