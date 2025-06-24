# Contributing

Contributions are always welcome and appreciated! Here are some ways you can contribute.

******
Issues
******

You can and should open an issue for any of the following reasons:

* you found a bug; steps for reproducing, or a pull request with a failing test case will be greatly appreciated
* you wanted to do something but did not find a way to do it after reading the documentation
* you believe the current way of doing something is more complicated or less elegant than it can be
* a related feature that you want is missing from the package

Please always check for existing issues before opening a new issue.

******
Pull requests
******

1. **Fork the repository on GitHub**
2. **Clone your fork and create a branch for the code you want to add**
3. **Install the package in development mode**

        $ pip install poetry
        $ poetry install

4. **Make your changes and check**
5. **Update the tests if necessary**
6. **Run tests. The project is setup to use pytest for testing**

        $ pytest

7. **Update documentation**
8. **Push your branch and submit a pull request to the main branch on GitHub**
9. **Your code must pass all the required CI jobs before it is merged**
