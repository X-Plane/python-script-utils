def to_implement(stub_function):
    def func_wrapper(*args, **kwargs):
        raise NotImplementedError(f'{stub_function.__name__}() is not yet implemented')

    return func_wrapper
