"""Module for generic testing of a 'dataset' derived from various sources.

    `generictests.run(check_manager, dataset)`

will run all possible tests on `dataset`, depending on what attributes
`dataset` has. Datasets can be derived from agentouputs, crashreports,
or specified as explicit modules (as in the datasets subpackage).

The minimal compliant dataset must have the attribute

  * `checkname` (str)       : The name of the (main) check.

In order to actually do something, at least one of the following attributes
must be present. They are optional (but you must provide some input for the
check function(s)). In the following, 'sc-dict' refers to a dictionary with
*s*ub*c*heck names as keys (and '' for the main check).

  * `info` (list)    : [list] The info variable as passed to the discovery (or
                       parse) function.
                       If `info` is present, the parse_function is applied (if
                       it exists). Otherwise it is used as input for the disco-
                       very and check functions.
  * `parsed`         : The result of the parse function.
                       If `parsed` is present, a parse function is required.
                       The result of parsing `info` (if present) must compare
                       equal to it.
                       Used as input for the discovery and check functions.
  * `discovery`      : [sc-dict] Expected discovery results.
                       If present, its values are lists of 2-tuples
                           (item, default_params).
                       The order of the lists does not matter.
  * `checks`         : [sc-dict] Expected check results.
                       If present, its values are lists of 3-tuples
                           (item, params, expected_results).
                      `expected_results` must be a valid argument for Check-
                      Result defined in checktestlib.

Some more advanced ones are

  * `extra_sections` : [sc-dict] Extra sections that are appended to the info
                       / parsed variable.
                       If present, its values are extra sections (the actual
                       content, not their names!) appended to the info/parsed
                       argument before passed to the discovery or check
                       function.
  * `mock_host_conf` : [sc-dict] If present, its values are passed to
                           `MockHostExtraConf`
                       as defined in checktestlib module.
  * `mock_item_state`: [sc-dict] If present, its values are passed to
                           `MockItemState`
                       as defined in checktestlib module.
"""
from generictests.checkhandler import checkhandler
from generictests.run import run
