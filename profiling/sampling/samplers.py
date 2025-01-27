# -*- coding: utf-8 -*-
"""
    profiling.sampling.samplers
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~
"""
from __future__ import absolute_import
import functools
import signal
import sys
import threading
import weakref

import six.moves._thread as _thread

from ..utils import Runnable, deferral, clock


__all__ = ['Sampler', 'ItimerSampler', 'TracingSampler']


INTERVAL = 1e-3  # 1ms


class Sampler(Runnable):
    """The base class for samplers."""

    #: Sampling interval.
    interval = INTERVAL

    def __init__(self, interval=INTERVAL):
        self.interval = interval

    @staticmethod
    def current_frames():
        return sys._current_frames()


class ItimerSampler(Sampler):

    # keep the Id of the math thread.
    main_thread_id = _thread.get_ident()

    def handle_signal(self, profiler, signum, frame):
        frames = self.current_frames()
        # replace frame of the main thread with the interrupted frame.
        frames[self.main_thread_id] = frame
        for frame_ in frames.values():
            profiler.sample(frame_)

    def run(self, profiler):
        weak_profiler = weakref.proxy(profiler)
        handle = functools.partial(self.handle_signal, weak_profiler)
        t = self.interval
        with deferral() as defer:
            prev_handle = signal.signal(signal.SIGPROF, handle)
            defer(signal.signal, signal.SIGPROF, prev_handle)
            prev_itimer = signal.setitimer(signal.ITIMER_PROF, t, t)
            defer(signal.setitimer, signal.ITIMER_PROF, *prev_itimer)
            yield


class TracingSampler(Sampler):

    sampled_at = 0

    def _profile(self, profiler, frame, event, arg):
        t = clock()
        if t - self.sampled_at < self.interval:
            return
        self.sampled_at = t
        frames = self.current_frames()
        frames[_thread.get_ident()] = frame
        for frame in frames.values():
            profiler.sample(frame)

    def run(self, profiler):
        profile = functools.partial(self._profile, profiler)
        with deferral() as defer:
            sys.setprofile(profile)
            defer(sys.setprofile, None)
            threading.setprofile(profile)
            defer(threading.setprofile, None)
            yield
