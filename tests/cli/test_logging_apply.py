from __future__ import annotations

import logging

from bioseq_dl.logging import get_logger, setup_logging


def test_setup_logging_applies_level_to_existing_logger():
    # logger created before the level change (mimics import-time module logger)
    pre = get_logger("bioseq_dl.cli.test_logging_apply")

    setup_logging("debug")
    assert logging.getLogger().level == logging.DEBUG
    assert pre.getEffectiveLevel() == logging.DEBUG

    setup_logging("error")
    assert logging.getLogger().level == logging.ERROR
    assert pre.getEffectiveLevel() == logging.ERROR

    setup_logging("info")  # restore default for other tests
