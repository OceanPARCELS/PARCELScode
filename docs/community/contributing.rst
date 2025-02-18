Contributing to Parcels
=======================

Why contribute?
---------------

`Lagrangian Ocean Analysis <https://doi.org/10.1016/j.ocemod.2017.11.008>`_ is one of the primary modelling tools available to oceanographers to understand how ocean currents transport material. This modelling approach allows researchers to model the ocean and understand the `movement of water <https://doi.org/10.1029/2023GL105662>`_ in the ocean itself (or even `on other planets <https://doi.org/10.3847/1538-4357/ac9d94>`_), as well as the transport of `nutrients <https://doi.org/10.1029/2023GL108001>`_, `marine organisms <https://doi.org/10.3354/meps14526>`_, `oil <https://doi.org/10.1590/0001-3765202220210391>`_, `plastic <https://doi.org/10.1038/s41561-023-01216-0>`_, as well as `almost <https://doi.org/10.1016/j.robot.2024.104730>`_ `anything <https://doi.org/10.1111/cobi.14295>`_ `else <https://doi.org/10.1016/j.marpolbul.2023.115254>`_ that would be adrift at sea. Since ocean currents play a key role in climate by storing heat and carbon, and also in the formation of the 'plastic soup', understanding transport phenomena in the ocean is crucial to support a more sustainable future.

The Parcels code, for which development started in 2015, is now one of the most widely used tools for Lagrangian Ocean Analysis. It's used by dozens of groups around the world - see `this list <https://oceanparcels.org/articles.html>`_ for a full list of the peer-reviewed articles using Parcels. Its flexibility for users to create new, custom 'behaviours' (i.e. let virtual particles be controlled by other mechanics than only the ocean flow) and its compatibility with many different types of hydrodynamic input data are the two key features.

.. note::

    Want to learn more about Lagrangian ocean analysis? Then look at `Lagrangian ocean analysis: Fundamentals and practices <https://www.sciencedirect.com/science/article/pii/S1463500317301853>`_ for a review of the literature.

----

There are two primary groups that contribute to Parcels; oceanographers who bring domain specific understanding about the physical processes and modelling approaches, as well as software developers who bring their experience working with code. **All contributions are welcome no matter your background or level of experience**.

.. note::

    The first component of this documentation is geared to those new to open source. Already familiar with GitHub and open source? Skip ahead to the `Editing Parcels code`_ section.

What is open source?
--------------------

Open source is a category of software that is open to the public, meaning that anyone is able to look at, modify, and improve the software. Compare this to closed source software (e.g., Microsoft Word, or Gmail) where only those working for the company on the product are able to look at the source code, or make improvements.

Software being open source allows bugs in the code to be quickly identified and fixed, as well as fosters communities of people involved on projects. Most open source software have permissible licenses making them free to modify, and use even in commercial settings. Parcels, for example, is open source and `licensed under the MIT License <https://github.com/OceanParcels/parcels/blob/main/LICENSE.md>`_.

This visibility of the codebase results in a higher quality, as well as a more transparent and stable product. This is important in research for reproducibility, as well as in industry where stability is crucial. Open source is not some niche category of software, but in fact `forms the backbone of modern computing and computing infrastructure <https://www.newstatesman.com/science-tech/2016/08/how-linux-conquered-world-without-anyone-noticing>`_ and is used widely in industry. A lot of the digital services that you use (paid, or free) depend on open source code in one way or another.

Most open source code is managed through a version control system called Git. Once you get past the Git specific terminology, the fundamental nature of it is quite understandable. To give an overview: Git, which you can install on your local machine, is a tool which allows you to create snapshots (aka., ”commits”) of a codebase. These snapshots each have a custom message attached to it, forming a time-line for the life of the project. This allows you to incrementally make updates to a codebase, while also having full control to undo any changes (you can even use Git to see which line of code was written by who).

A codebase (in Git terms, this is called a “repository” or “repo” for short) can be uploaded to a platform such as GitHub for hosting purposes, allowing for multiple people to be involved in a project. These platforms add a social media and project management aspect, where tasks can be created (these tasks are called “issues”, and can represent bugs, suggested features, or documentation improvements), assigned to people, and be addressed in changes to the codebase (i.e., addressed in a “pull request”, which details exactly which parts of the codebase need to change to fix a particular issue). A common workflow is for an issue to be created, discussed, and then addressed by one or more pull requests.

Exactly how to use Git and GitHub is beyond the scope of this documentation, and there are many tutorials online on how to do that (here are some good ones: `Version Control with Git by Software carpentry <https://swcarpentry.github.io/git-novice/>`_,  `Learn Git by freeCodeCamp.org <https://www.youtube.com/watch?v=zTjRZNkhiEU>`_).

Your first contribution
-----------------------

There are many ways that you can contribute to Parcels. You can:

- Participate in discussion about Parcels, either through the `issues <https://github.com/OceanParcels/parcels/issues>`_ or `discussions <https://github.com/OceanParcels/parcels/discussions>`_ tab
- Suggest improvements to `tutorials <../documentation/index.rst>`_
- Suggest improvements to `documentation <../index.rst>`_
- Write code (fix bugs, implement features, codebase improvements, etc)

All of these require you to make an account on GitHub, so that should be your first step.

If you want to suggest quick edits to the documentation, it's as easy as going to the page and clicking "Edit on GitHub" in the righthand panel. For other changes, it's a matter of looking through the `issue tracker <https://github.com/OceanParcels/parcels/issues>`_ which documents tasks that are being considered. Pay particular attention to `issues tagged with "good first issue" <https://github.com/OceanParcels/parcels/issues?q=is%3Aopen+is%3Aissue+label%3A%22good+first+issue%22>`_, as these are tasks that don't require deep familiarity with the codebase. Once you've chosen an issue you would like to contribute towards, comment on it to flag your interest in working on it. This allows the community to know who's interested, and provide any guidance in its implementation (maybe the scope has changed since the issue was last updated).

If you're having trouble using Parcels, feel free to create a discussion in our Discussions tab and we'll be happy to support. Want to suggest a feature, or have encountered a problem that is a result of a bug in Parcels, then search for an issue in the tracker or `create a new one <https://github.com/OceanParcels/parcels/issues/new/choose>`_ with the relevant details.

In the `Projects panel <https://github.com/OceanParcels/parcels/projects?query=is%3Aopen>`_, you'll see the "Parcels development" project. This is used by the core development team for project management, as well as drafting up new ideas for the codebase that aren't mature enough to be issues themselves. Everything in "backlog" is not being actively worked on and is fair game for open source contributions.

.. _editing-parcels-code:

Editing Parcels code
---------------------

Development environment setup
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

To get started contributing to Parcels:

- `fork the repo <https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/working-with-forks/fork-a-repo#forking-a-repository>`_
- install the developer version of Parcels following `our developer installation instructions <../installation.rst#installation-for-developers>`_
    - but instead of cloning the Parcels repo, you should clone your fork

Now you have a cloned repo that you have full control over, and a conda environment where Parcels is installed in an editable mode (i.e., any changes that you make to the Parcels code will take effect when you use that conda environment to run Python code).

From there:

- create a git branch, implement, commit, and push your changes
- `create a pull request <https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/proposing-changes-to-your-work-with-pull-requests/creating-a-pull-request-from-a-fork>`_ (PR) into ``main`` of the original repo making sure to link to the issue that you are working on. Not yet finished with your feature but still want feedback on how you're going? Then mark it as "draft" and ``@ping`` a maintainer. See our `maintainer notes <maintainer.md>`_ to see our PR review workflow.

Here is a short overview of a few different commands that we use during development:

.. code-block:: bash

   # Run unit-tests
   pytest

   # Run typechecking
   mypy

   # Build the documentation. This launches a server, automatically rebuilt when changes are made
   sphinx-autobuild --ignore "*.zip" docs docs/_build


To run performance benchmarks, see the `the benchmarking page <benchmarking.md>`_.

Code guidelines
~~~~~~~~~~~~~~~

.. note::

    These guidelines are here to promote Python best practices, as well as standardise the Parcels code. If you're not sure what some of these guidelines mean, don't worry! Your contribution is still appreciated. When you create your pull request, maintainers can modify your code to comply with these guidelines.

- Write clear commit messages that explain the changes you've made.
- Include tests for any new code you write. Tests are implemented using pytest and are located in the ``tests`` directory.
- Follow the `NumPy docstring conventions <https://numpydoc.readthedocs.io/en/latest/format.html>`_ when adding or modifying docstrings.
- Follow the `PEP 8 <https://peps.python.org/pep-0008/>`_ style guide when writing code. This codebase also uses `flake8 <https://flake8.pycqa.org/en/latest/>`_ and `isort <https://pycqa.github.io/isort/>`_ to ensure a consistent code style.

If you're comfortable with these code guidelines, and want to enforce them on your local machine before pushing, you can install the Git hooks for the repo by running ``pre-commit install``. This will run tools to check your changes adhere to these guidelines as you make commits.

----

That's it! Thank you for reading and we'll see you on GitHub 😁.
