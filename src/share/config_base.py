from decouple import config


class ConfigBase(object):

    DEBUG = config('DEBUG', default=False, cast=bool)




