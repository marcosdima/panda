from panda3d.core import ClockObject


from .__global import Global


class GlobalClock(Global):
    ''' A singleton class to manage the global clock object. '''
    _global_clock = ClockObject.getGlobalClock()

    
    @classmethod
    def get_dt(cls) -> float:
        '''Get the delta time from the global clock.'''
        return cls._global_clock.getDt()
