if __name__=='__main__':
    import sys
    version = sys.stdin.readline().rstrip()
    if '(' in version and ')' in version:
        version = version[1:4]
        print(f"{str(float(version)+0.02)[0:5]}")