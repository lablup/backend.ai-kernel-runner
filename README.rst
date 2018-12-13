Backend.AI Kernel Runner
========================

A common base runner for various programming languages.

It manages an internal task queue so that multiple command/code execution requests
are processed in the FIFO order, without garbling the console output.


How to write a new computation kernel
-------------------------------------

Inherit ``ai.backend.kernel.BaseRunner`` and implement the following methods:

* ``async def init_with_loop(self)``

  - Called after the asyncio event loop becomes available.

  - Mostly just ``pass``.

  - If your kernel supports interactive user input, then put set
    ``self.user_input_queue`` as an ``asyncio.Queue`` object.  It's your job
    to utilize the queue object for waiting for the user input.  (See
    ``handle_input()`` method in ``ai/backend/kernel/python/inproc.py`` for
    reference)  If it's not set, then any attempts for getting interactive user
    input will simply return ``"<user-input is unsupported>"``.

* ``async def build_heuristic(self)``

  - *(Batch mode)* Write a heuristic code to find some build script or run a
    good-enough build command for your language/runtime.

  - *(Blocking)* You don't have to worry about overlapped execution since the
    base runner will take care of it.

* ``async def execute_heuristic(self)``

  - *(Batch mode)* Write a heuristic code to find the main program.

  - *(Blocking)* You don't have to worry about overlapped execution since the
    base runner will take care of it.

* ``async def query(self, code_text)``

  - *(Query mode)* Directly run the given code snippet. Depending on the language/runtime,
    you may need to create a temporary file and execute an external program.

  - *(Blocking)* You don't have to worry about overlapped execution since the
    base runner will take care of it.

* ``async def complete(self, data)``

  - *(Query mode)* Take a dict data that includes the current line of code where
    the user is typing and return a list of strings that can auto-complete it.

  - *(Non-blocking)* You should implement this method to run asynchronously with
    ongoing code execution.

* ``async def interrupt(self)``

  - *(Query mode)* Send an interruption signal to the running program. The implementation
    is up to you. The Python runner currently spawns a thread for in-process
    query-mode execution and use a ctypes hack to throw KeyboardInterrupt
    exception into it.

  - *(Non-blocking)* You should implement this method to run asynchronously with
    ongoing code execution.

* ``async def start_service(self, service_info)``

  - If your kernel supports long-running service daemons, start them here.
    (e.g., Jupyter, TensorBoard, OpenSSH, etc.)
    A runner subclass simply returns the command arguments as a list and other stuffs
    will be taken care by the ``BaseRunner``.

  - The ``service_info`` is a dict composed of the following keys extracted from
    the ``ai.backend.service-ports`` image label:

    - ``name``: The name of service so that you could distinguish which command to
      execute.

    - ``protocol``: The type of service protocol such as ``"pty"``, ``"tcp"`` and
      ``"http"``.

    - ``port``: The container-side port number to use. The manager/agent has already
      took care of the dynamic binding of this port outside.

    - ``options``: An optional dict that contains extra options for the service.


NOTE: Existing codes are good referecnes!


How to use in your Backend.AI computation kernels
-------------------------------------------------

Install this package using pip via a ``RUN`` instruction in Dockerfile.
Then, set the ``CMD`` instruction like below:

.. code-block:: dockerfile

   CMD ["/home/backend.ai/jail", "-policy", "/home/backend.ai/policy.yml", \
        "/usr/local/bin/python", "-m", "ai.backend.kernel", "<language>"]

where ``<language>`` should be one of the supported language names defined in
``lang_map`` variable in ``ai/backend/kernel/__main__.py`` file.
