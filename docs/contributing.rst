How to Contribute
=================
Do you want to contribute fixes or improvements?

   **AWesome!** *Thank you very much, and let's get started.*

This project uses hatch_ for project automation and pre-commit_ to ensure that your
changes aren't going to be rejected for formatting or style reasons.  However, you do
need to install both utilities.  You should install it using a specific python version
as a "user" installation.::

    python3.10 -m pip install --user hatch pre-commit

This will install the utility into ``~/.local/bin`` which you may need to add to
your ``PATH`` environment variable.

.. note::

   You are not required to use ``hatch`` or ``pre-commit`` to contribute to this
   project.  Using them will make your life a little easier though.  The following
   sections contain instructions for using a completely vanilla Python virtual
   environment which can be adapted to your workflow.

Testing
-------
The simplest way to run the tests with coverage is from within a hatch-spawned shell::

    $ hatch shell
    (sprockets-http)$ coverage run -m pytest tests.py
    (sprockets-http)$ coverage report

You can also run the same commands without using an interactive hatch spawned shell::

    $ hatch run coverage run -m pytest tests.py
    $ hatch run coverage report

Finally, you can simply extract the development requirements using hatch and use a
vanilla virtual environment::

    $ python3.11 -m venv --upgrade-deps env
    $ . ./env/bin/activate
    (env) $ pip install hatch
    (env) $ hatch dep show requirements --all >requirements.txt
    (env) $ pip install -r requirements.txt
    (env) $ coverage run -m pytest tests.py
    (env) $ coverage report

Linting
-------
Lint checking is off-loaded to the pre-commit_ utility.  After installing the hooks,
any commit is blocked by style checks.  You can also run the hooks manually using the
pre-commit_ utility.
::

    $ pre-commit install --install-hooks
    $ pre-commit run --all-files

Of course, you can run ``flake8`` and ``yapf`` manually inside of a vanilla environment::

    (env) $ flake8 docs sprockets examples.py tests.py
    (env) $ yapf -dr docs sprockets examples.py tests.py

.. _hatch: https://hatch.pypa.io/latest/
.. _pre-commit: https://pre-commit.com/
