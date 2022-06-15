def validate_float(func):
    def wrapper(*args, **kwargs):
        # Check if the input is None
        for arg in args:
            if arg is None:
                raise ValueError("Input cannot be None")
        args = map(float, args)
        return func(*args, **kwargs)
    return wrapper
