import time


def main():
    start_time = time.time()

    variable = time.time()

    while time.time() - start_time < 12 * 60 * 60:
        variable = time.time()
        time.sleep(1)


if __name__ == "__main__":
    main()

