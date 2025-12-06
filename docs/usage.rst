Usage Overview
==============

The CLI entry point is ``badc``. Today it exposes a placeholder ``version`` command and a
``data`` namespace that will eventually orchestrate DataLad datasets::

    $ badc version
    BADC version: 0.1.0

    $ badc data connect bogus
    TODO: implement DataLad clone/register logic.

The commands run locally without GPU dependencies so we can test the scaffolding in CI.
