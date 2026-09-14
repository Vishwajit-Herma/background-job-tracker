"""Optimized RedisChannelLayer for Django Channels."""

from channels_redis.core import RedisChannelLayer


class LowCommandRedisChannelLayer(RedisChannelLayer):
    """
    Extends RedisChannelLayer to lengthen the internal brpop_timeout from 5s to 25s,
    reducing idle WebSocket polling commands (EVAL, DEL, BZPOPMIN) by 80%.
    """

    brpop_timeout = 25
