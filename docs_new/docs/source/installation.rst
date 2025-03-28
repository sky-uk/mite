===========
Set up Mite
===========

We use and test mite on Mac machine and previously on linux machines. 
At the current time everything runs from terminal 

Installation
============

.. code-block:: sh

    pip install mite
    

This requires that you have libcurl installed on your system (including C header files for development, which are often distributed separately from the shared libraries). On Ubuntu, this can be accomplished with the command:

.. code-block:: sh

    sudo apt install libcurl4 libcurl4-openssl-dev


.. admonition:: info
    :class: note 
    
    we recommend using a version of libcurl linked against openssl rather than gnutls, since the latter has memory leak problems)


You can also use the dockerfile included in this repository to run mite. In order to get a shell in a container with mite installed, run these commands (assuming you have docker installed on your machine):

.. code-block:: sh

    docker build -t mite .
    docker run --rm -it mite sh


Run mite --help for a full list of commands

