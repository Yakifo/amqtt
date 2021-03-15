# Copyright (c) 2015 Nicolas JOUANIN
#
# See the file license.txt for copying permission.

from setuptools import setup, find_packages

setup(
    name="amqtt",
    version="0.10.0-alpha.1",
    description="MQTT client/broker using Python asyncio",
    author="aMQTT Contributers (https://github.com/Yakifo/amqtt/graphs/contributors)",
    url="https://github.com/Yakifo/amqtt",
    license="MIT",
    packages=find_packages(exclude=["tests"]),
    include_package_data=True,
    platforms="all",
    install_requires=["transitions", "websockets", "passlib", "docopt", "pyyaml"],
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: POSIX",
        "Operating System :: MacOS",
        "Operating System :: Microsoft :: Windows",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Topic :: Communications",
        "Topic :: Internet",
    ],
    entry_points={
        "hbmqtt.test.plugins": [
            "test_plugin = tests.plugins.test_manager:TestPlugin",
            "event_plugin = tests.plugins.test_manager:EventTestPlugin",
            "packet_logger_plugin = hbmqtt.plugins.logging:PacketLoggerPlugin",
        ],
        "hbmqtt.broker.plugins": [
            # 'event_logger_plugin = hbmqtt.plugins.logging:EventLoggerPlugin',
            "packet_logger_plugin = hbmqtt.plugins.logging:PacketLoggerPlugin",
            "auth_anonymous = hbmqtt.plugins.authentication:AnonymousAuthPlugin",
            "auth_file = hbmqtt.plugins.authentication:FileAuthPlugin",
            "topic_taboo = hbmqtt.plugins.topic_checking:TopicTabooPlugin",
            "topic_acl = hbmqtt.plugins.topic_checking:TopicAccessControlListPlugin",
            "broker_sys = hbmqtt.plugins.sys.broker:BrokerSysPlugin",
        ],
        "hbmqtt.client.plugins": [
            "packet_logger_plugin = hbmqtt.plugins.logging:PacketLoggerPlugin",
        ],
        "console_scripts": [
            "hbmqtt = hbmqtt.scripts.broker_script:main",
            "hbmqtt_pub = hbmqtt.scripts.pub_script:main",
            "hbmqtt_sub = hbmqtt.scripts.sub_script:main",
        ],
    },
)
