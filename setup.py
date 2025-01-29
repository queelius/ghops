setup(
    name="ghops",
    version="0.1.0",
    packages=["ghops"],
    install_requires=[
        "rich>=13.0.0",
        "pathlib"
    ],
    entry_points={
        "console_scripts": [
            "ghops=ghops.__main__:main",
        ]
    },
  )
