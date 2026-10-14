for pkg in ["playwright", "selenium", "pyppeteer"]:
    try:
        __import__(pkg)
        print(f"{pkg}: INSTALLED")
    except ImportError:
        print(f"{pkg}: not installed")
