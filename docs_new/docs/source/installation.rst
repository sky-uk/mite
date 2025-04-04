===========
Set up Mite
===========

We use and test mite on MacOs machines and we previously did on Linux VMs. 
At the current time everything runs from the terminal.

Installation
============

.. code-block:: sh

    pip install mite
    

This requires that you have libcurl installed on your system (including C header files for development, which are often distributed separately from the shared libraries). On Ubuntu, this can be accomplished with the command:

.. code-block:: sh

    sudo apt install libcurl4 libcurl4-openssl-dev


.. admonition:: openssl VS gnutls
    :class: note 
    
    We personally use a version of *libcurl* linked against *openssl* rather than *gnutls*. Mostly because in the past the latter had an issues with high memory usage.
    Now that the issue has been resolved, even if we still prefer to use *openssl*, feel free to use which-ever you prefer. 


To run mite, you can also use the dockerfile included in this repository to run mite. In order to get a shell in a container with mite installed, run these commands (assuming you have docker installed on your machine):

.. code-block:: sh

    docker build -t mite .
    docker run --rm -it mite sh


Run the ``mite --help`` command for a full list of commands.

