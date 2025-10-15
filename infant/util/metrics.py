class Metrics:
    """
    Metrics class can record various metrics during running and evaluation.
    Currently we define the following metrics:
        accumulated_cost: the total cost (USD $) of the current LLM.
    """

    def __init__(self) -> None:
        self._accumulated_cost: float = 0.0
        self._costs: list[float] = []

        # Track costs per function
        self._function_costs: dict[str, float] = {}

    @property
    def accumulated_cost(self) -> float:
        return self._accumulated_cost

    @accumulated_cost.setter
    def accumulated_cost(self, value: float) -> None:
        if value < 0:
            raise ValueError('Total cost cannot be negative.')
        self._accumulated_cost = value

    @property
    def costs(self) -> list:
        return self._costs

    def add_cost(self, value: float) -> None:
        if value < 0:
            raise ValueError('Added cost cannot be negative.')
        self._accumulated_cost += value
        self._costs.append(value)

    # add add_function_cost function
    def add_function_cost(self, function_name: str, cost: float) -> None:
        """
        Add cost for a specific function
        """
        if cost < 0:
            raise ValueError('Added cost cannot be negative.')
        self._function_costs[function_name] = self._function_costs.get(function_name, 0.0) + cost 
        self.add_cost(cost)

    # add get_function_costs function
    def get_function_costs(self) -> dict:
        """
        Get costs grouped by function name

        """
        return {
            func: round(cost, 6)
            for func, cost in self._function_costs.items()
        }

    def get(self):
        """
        Return the metrics in a dictionary.
        """
        return {
            'accumulated_cost': self._accumulated_cost, 
            'costs': self._costs,
            'function_costs': self.get_function_costs()
        }

    def log(self):
        """
        Log the metrics.
        """
        metrics = self.get()
        logs = ''
        for key, value in metrics.items():
            logs += f'{key}: {value}\n'
        return logs
    
    # FIXME: Implement a function here to calculate the total cost for each function. 
    # Input: function signature, output: total cost for the function.
