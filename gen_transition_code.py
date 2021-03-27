import pathlib


template = """import warnings
from {module_name} import *

warnings.warn("importing hbmqtt is deprecated. Please import amqtt", DeprecationWarning)
"""


def main():
    src = pathlib.Path("amqtt")
    dst = pathlib.Path("hbmqtt")

    for py_file in src.glob("**/*.py"):

        file_path = py_file.parent.relative_to(src)
        dst_file = dst / file_path / py_file.name
        module_name = "amqtt"
        sub_modue = str(file_path).replace("/", ".").strip(".")
        if sub_modue:
            module_name += "." + sub_modue

        if py_file.name != "__init__.py":
            module_name += "." + py_file.name[:-3]

        dst_file.parent.mkdir(parents=True, exist_ok=True)
        dst_file.write_text(template.format(module_name=module_name))


if __name__ == "__main__":
    main()
