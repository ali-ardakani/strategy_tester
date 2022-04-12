class Indicator:
    """ Indicator class.
    
    Description:
        This class is used to create an indicator for use in class IndicatorsParallel.
    """
    def __init__(self, name:str, func:callable, args=None, wait=True, **kwargs):
        """ Initialize the indicator """
        self.name = name
        self.func = func
        self.wait = wait
        self.args = args
        self.kwargs = kwargs
        
    def __repr__(self) -> str:
        return self.name
    
    def __str__(self) -> str:
        return self.name

    def __call__(self):
        return self.func(*self.args, **self.kwargs).rename(self.name)