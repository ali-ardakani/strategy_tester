from multiprocessing import Process, Queue, Manager
from .indicator import Indicator
import os

class IndicatorsParallel:
    """
    Class to run indicators in parallel.
    
    Description
    -----------
    This class calculates the indicators in multiple processes.
    """
    manager = Manager()
    
    def _init_indicator(self):
        self.processes = {}
        self.list_of_indicators = []
        self.results = {}
        self.returns = self.manager.dict()
        
    def add(self, *indicators):
        """
        Add indicators to the list.
        """
        self.list_of_indicators.extend(indicators)
       
    def _wrapper(self, indicator:Indicator):
        """
        Wrapper function to run indicators in a separate process.
        
        Parameters
        ----------
        indicator : strategy_tester.indicator.indicator.Indicator
            Indicator to run.
        queue : multiprocessing.Queue
            Queue to send results to.
        """
        indicator.args = list(indicator.args)
        for index, arg in enumerate(indicator.args):
            if isinstance(arg, Indicator):
                while True:
                    indicator_arg = self.returns.get(arg.name, False)
                    if type(indicator_arg) != bool:
                        break
                indicator.args[index] = indicator_arg
        self.returns[indicator.name] = indicator()

    def _live(self, name:str):
        """
        Check if indicator is running."""
        return self.processes[name].is_alive()
    
    # def _start(self):
    #     """
    #     Run indicators in parallel.
    #     """
    #     indicators_wait = self.__format__("wait")
    #     queue_wait = Queue()
    #     if indicators_wait:
    #         for indicator in indicators_wait:
    #             p = Process(target=self._wrapper, args=(indicator, queue_wait))
    #             p.start()
    #         self._set_indicators(queue_wait, indicators_wait)
    #         self._remove_indicators(indicators_wait)
    #     indicators_n_wait = self.__format__("n-wait")
    #     queue_n_wait = Queue()
    #     if indicators_n_wait:
    #         for indicator in indicators_n_wait:
    #             p = Process(target=self._wrapper, args=(indicator, queue_n_wait))
    #             p.start()
    #         self._set_indicators(queue_n_wait, indicators_n_wait)
    #         self._remove_indicators(indicators_n_wait)

    def _start(self):
        """
        Run indicators in parallel.
        """
        for indicator in self.list_of_indicators:
            p = Process(target=self._wrapper, args=(indicator,))
            p.start()
            print("Started indicator: {}".format(indicator.name))
            self.processes[indicator.name] = p

        # list_i = self.list_of_indicators
        self._set_indicators()
        self._remove_indicators(self.list_of_indicators)
            
    def _remove_indicators(self, indicators: list):
        """
        Remove indicators.
        """
        self.list_of_indicators = list(set(self.list_of_indicators) - set(indicators))
    
    def _set_indicators(self):
        """
        Set indicators.
        """
        for process in self.processes:
            if self.processes[process].is_alive():
                self.processes[process].join()
            self.__dict__[process] = self.returns[process]
    
        
    def start(self):
        """
        Return results of indicators.
        """
        if not self.list_of_indicators:
            raise ValueError("No indicators added.")
        self._start()
            
    def get_indicator(self, name:str):
        """
        Return indicator by name.
        """
        return self.__dict__.get(name)
    
    def __format__(self, __format_spec: str) -> list:
        """ Filter indicators by format spec. """
        if __format_spec == "n-wait":
            return [indicator for indicator in self.list_of_indicators if not indicator.wait]
        
        elif __format_spec == "wait":
            return [indicator for indicator in self.list_of_indicators if indicator.wait]

    @staticmethod
    def check_pid(pid):        
        """ Check For the existence of a unix pid. """
        try:
            os.kill(pid, 0)
        except OSError:
            return True
        else:
            return False
