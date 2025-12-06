Usage Overview
==============

The CLI entry point is ``badc``. Today it exposes a placeholder ``version`` command and a
``data`` namespace that will eventually orchestrate DataLad datasets. Early chunking helpers are
also available::

    $ badc version
    BADC version: 0.1.0

    $ badc data connect bogus
    TODO: implement DataLad clone/register logic.

    $ badc chunk probe data/audio/XXXX-000_20251001_093000.wav --initial-duration 120
    Probe placeholder: max chunk 120.00s for ...

The commands run locally without GPU dependencies so we can test the scaffolding in CI.
