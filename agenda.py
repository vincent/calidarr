import os
import pytz
import sys, getopt
from src.Calidarr import CalendarHandler
 
def main(argv):
    countries = []
    names = []
    try:
        opts, args = getopt.getopt(argv, "hc:n:", ["countries=","names="])
    except getopt.GetoptError:
        print ('agenda.py -c <countries> -n <names>')
        sys.exit(2)
    for opt, arg in opts:
        if opt == '-h':
            print ('agenda.py -c <countries> -a <names>')
            sys.exit()
        elif opt in ("-c", "--countries"):
            countries = arg.split(",")
        elif opt in ("-n", "--names"):
            names = arg.split(",")

    cal = CalendarHandler()
    print(cal.display(countries, names))

if __name__ == "__main__":
    main(sys.argv[1:])
