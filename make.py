from makepyz import api

@api.task()
def info(arguments):
    print("arguments.")
    for argument in arguments:
        print(f"  {argument}")