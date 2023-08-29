from logging import *

file_log = FileHandler("msufpbot.log")
console_out = StreamHandler()

formatter = Formatter("[%(asctime)s] %(levelname)s: %(message)s", "%d.%m.%Y, %H:%M:%S")
file_log.setFormatter(formatter)
console_out.setFormatter(formatter)

basicConfig(handlers=[file_log, console_out], level=DEBUG)
