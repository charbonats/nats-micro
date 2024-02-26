import argparse

from typing_extensions import TypeAlias

Subparser: TypeAlias = (
    argparse._SubParsersAction[  # pyright: ignore[reportPrivateUsage]
        argparse.ArgumentParser
    ]
)
