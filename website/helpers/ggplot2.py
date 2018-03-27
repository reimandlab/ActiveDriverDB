from rpy2.robjects.packages import importr


class GG:
    def __init__(self, plot):
        ggplot2 = importr("ggplot2")
        self.plot = plot
        self.add = ggplot2._env['%+%']

    def __add__(self, other):
        return GG(self.add(self.plot, other))
