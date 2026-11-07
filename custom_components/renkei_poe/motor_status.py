"""Motion flags shared by vendor and in-house RENKEI firmware."""

from enum import IntEnum


class MotorMotion(IntEnum):
    """The low two bits of the legacy GET_STATUS run_flags byte."""

    STOPPED = 0
    OPENING = 1
    CLOSING = 2


def motor_motion(run_flags: object) -> MotorMotion | None:
    """
    Decode valid flags without treating missing or reserved values as stopped.
    """
    if type(run_flags) is not int or not 0 <= run_flags <= 255:
        return None
    try:
        return MotorMotion(run_flags & 0x03)
    except ValueError:
        return None
