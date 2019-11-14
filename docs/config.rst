==========================================
Specifying configuration for mite journeys
==========================================

All mite journey functions are passed a ``config`` property on their
``context`` argument.  This implements a generic key-value storage
system for managing journey configuration.  Journey functions can call
``context.config.get("key")`` to retrieve the value set for a given key.

Managing configuration in this way, rather than as values in python
files, has several advantages:

- It is easy to parameterize tests for different environments
- Sensitive data (IP addresses, passwords) can be stored separately from
  test journey code and encrypted (we use `git-crypt`_ for this purpose
  in a dedicated journeys-and-scenarios repository at Sky, where our
  tests need to use auth credentials to talk to some of the endpoints we
  test).
- The configuration can be dynamically modified by scenario functions

.. _git-crypt: https://github.com/AGWA/git-crypt

There are several ways to provide configuration values to mite when it
is invoked, which are explained in the following sections

Via environment variables
-------------------------

By default, if no other configuration is specified, mite looks in the
process environment.  All environment variables with names of the form
``MITE_CONF_key`` are mapped to config entries under ``key``.  This
method is convenient for use at the command line when testing journeys.
It also combines well with certain external config/secret management
solutions that are designed to work with environment variables (for
instance, `kubernetes secrets`_).

.. _kubernetes secrets: https://kubernetes.io/docs/concepts/configuration/secret/#using-secrets-as-environment-variables

Via a python callable
---------------------

Similarly to the way that scenarios and journeys are specified as a
string of ``python.module:name_in_module``, configuration may also be
specified in the same way with the ``--config`` command line argument.
The python object pointed to in this way should be a function which
returns a dictionary of configuration.

Single values on the command line
---------------------------------

It is also possible to set single config values on the command line,
using the argument ``--add-to-config=key:value``.  This will add a
setting of ``key`` to ``value`` in the existing configuration which
has already been set by one of the above two methods.

Dynamically in the scenario function
------------------------------------

The scenario function, if it accepts an argument, will be passed the
config object.  The scenario function can then call
``config.set("key", "value")`` in order to change values in the
configuration.

Some of what this functionality accomplishes could be duplicated by the
callable-returning-dictionary config method above.  However, there are
advantages to the redundancy.  We have tended to use the
callable-returning-dictionary method for storing configuration related
to the system under test (including sensitive information that is
encrypted).  We use the dynamic setting of config in the scenario
function to set config values that are related to the load profile of
the test.  The latter information is more logically placed in the
scenario function (which also manages the load profile in other ways,
such as through the volume model).  It also brings the benefit of not
being encrypted, so that this code can benefit from the full versioning
capabilities of our SCM.
