# -*- coding: utf-8 -*-
"""
    profiling.tracing.timers
    ~~~~~~~~~~~~~~~~~~~~~~~~
"""
from __future__ import absolute_import
import sys
import time

from ..utils import Runnable, lazy_import, clock


__all__ = ['Timer', 'ContextualTimer', 'ThreadTimer', 'GreenletTimer']


class Timer(Runnable):
    """The basic timer."""

    def __call__(self):
        #: The raw function to get the CPU time.
        return clock()

    def run(self, profiler):
        yield


class ContextualTimer(Timer):

    def __new__(cls, *args, **kwargs):
        timer = super(ContextualTimer, cls).__new__(cls, *args, **kwargs)
        timer._contextual_times = {}
        return timer

    def __call__(self, context=None):
        if context is None:
            context = self.detect_context()
        paused_at, resumed_at = self._contextual_times.get(context, (0, 0))
        if resumed_at is None:  # paused
            return paused_at
        return paused_at + clock() - resumed_at

    def pause(self, context=None):
        if context is None:
            context = self.detect_context()
        self._contextual_times[context] = (self(context), None)

    def resume(self, context=None):
        if context is None:
            context = self.detect_context()
        paused_at, __ = self._contextual_times.get(context, (0, 0))
        self._contextual_times[context] = (paused_at, clock())

    def detect_context(self):
        raise NotImplementedError('detect_context() should be implemented')


class ThreadTimer(Timer):
    """A timer to get CPU time per thread.  Python 3.3 or later uses the
    built-in :mod:`time` module.  Earlier Python versions requires `Yappi`_ to
    be installed.

    .. _Yappi: https://code.google.com/p/yappi/
    """

    if sys.version_info < (3, 3):
        yappi = lazy_import('yappi')
        def __call__(self):
            return self.yappi.get_clock_time()
    else:
        def __call__(self):
            return time.clock_gettime(time.CLOCK_THREAD_CPUTIME_ID)


class GreenletTimer(ContextualTimer):
    """A timer to get CPU time per greenlet."""

    greenlet = lazy_import('greenlet')

    def detect_context(self):
        if self.greenlet:
            return id(self.greenlet.getcurrent())

    def _trace(self, event, args):
        origin, target = args
        self.pause(id(origin))
        self.resume(id(target))

    def run(self, profiler):
        self.greenlet.settrace(self._trace)
        yield
        self.greenlet.settrace(None)
