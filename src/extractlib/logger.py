import logging

class Color:
  BLACK = "\033[30m"
  RED = "\033[31m"
  GREEN = "\033[32m"
  YELLOW = "\033[33m"
  BLUE = "\033[34m"
  PURPLE = "\033[35m"
  CYAN = "\033[36m"
  WHITE = "\033[37m"
  END = "\033[0m"
  BOLD = "\033[1m"
  UNDERLINE = "\033[4m"
  INVISIBLE = "\033[08m"
  REVERSE = "\033[07m"


class ColoredFormatter(logging.Formatter):
  def format(self, record: logging.LogRecord):
    prefix = ""
    if record.levelno < logging.INFO:
      prefix = f"{Color.BOLD}[*]{Color.END} "
    elif record.levelno < logging.WARNING:
      prefix = f"{Color.BOLD}{Color.GREEN}[*]{Color.END} "
    elif record.levelno < logging.ERROR:
      prefix = f"{Color.BOLD}{Color.YELLOW}[+]{Color.END} "
    else:
      prefix = f"{Color.BOLD}{Color.RED}[+]{Color.END} "
    return prefix + super(ColoredFormatter, self).format(record)


logger = logging.getLogger("extract-lib")
logger.setLevel(logging.INFO)

if not logger.hasHandlers():
  handler = logging.StreamHandler()
  formatter = ColoredFormatter("%(message)s [%(pathname)s:%(lineno)d]")
  handler.setFormatter(formatter)
  logger.addHandler(handler)
