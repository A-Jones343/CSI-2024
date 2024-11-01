import json
import pandas as pd
import math


class Obj:
    machine = ""
    id = 0
    pullrate = None
    plies = None
    grade = None
    scrapFactor = 0
    po = None
    quantity = 0
    conversion = 0
    demand = 0
    rate = 0
    feetPerLog = None
    rollPerLog = None
    sheetWidth = None

    def __init__(self, machine, id):
        self.machine = machine
        self.id = id

class Avail:
    machine = ""
    po = ""

    startIPO = 0
    endIPO = 0
    startReserve = 0
    endReserve = 0

    id = 0
    quantity = 0
    grade = ""
    asset = 0

    def __init__(self, asset, machine):
        self.asset = asset
        self.machine = machine

def Reader(Foldername):
    list = []

    # Reads in SKU_Pull_Rate_Dict
    with open("C:\\Users\\ajone\\OneDrive\\Desktop\\HackathonPackageV2\\HackathonPackageV2\\DataCache\\OptimizerSituations\\" + Foldername + "\\SKU_Pull_Rate_Dict.json", 'r') as f:
        data = json.load(f)

    for machine, attribute in data.items():
        for id, field in attribute.items():
            obj = Obj(machine, id)
            for key, val in field.items():
                if(key == "PullRate"):
                    obj.pullrate = val

                if(key == "Plies"):
                    obj.plies = val

                if(key == "Grade"):
                    obj.grade = val

            list.append(obj)
    f.close()

    # Reads in scrapFactor
    with open("C:\\Users\\ajone\\OneDrive\\Documents\\GitHub\\CSI-2024\\DataCache\\OptimizerSituations\\" + Foldername + "\\scrapFactor.json", 'r') as f:
        data = json.load(f)
    
    for attribute in list:
        for key, val in data.items():
            if(attribute.grade == key):
                attribute.scrapFactor = val              
    f.close()

    # Reads in planningRateDict
    with open("C:\\Users\\ajone\\OneDrive\\Documents\\GitHub\\CSI-2024\\DataCache\\OptimizerSituations\\" + Foldername + "\\planningRateDict.json", 'r') as f:
        data = json.load(f)
    
    for machine, val in data.items():
        for attribute, field in val.items():
            for obj in list:
                if(obj.id == attribute and obj.machine == machine):
                    obj.rate = field
    f.close()


# Reads in SKU_Converting_Specs_Dict
    with open("C:\\Users\\ajone\\OneDrive\\Documents\\GitHub\\CSI-2024\\DataCache\\OptimizerSituations\\" + Foldername + "\\SKU_Converting_Specs_Dict.json", 'r') as f:
        data = json.load(f)

    for machine, attribute in data.items():
        for id, field in attribute.items():
            for obj in list:
                if(obj.id == id and obj.machine == machine):
                    for key, val in field.items():
                        if(key == "Feet/Log"):
                            obj.feetPerLog = val
                        elif(key == "Rolls/Log"):
                            obj.rollPerLog = val
                        elif(key == "CFR1 Sheet Width"):
                            obj.sheetWidth = val




    columnName = ["Machine", "ID", "PullRate", "Plies", "Grade", "ScrapFactor", "Quantity", "ProductPerMinute", "FeetPerLog", "RollPerLog", "SheetWidth"]# "DemandConversion", "Demand"]

    #pd.set_option('display.max_rows', None)
    
    df = pd.DataFrame(columns=columnName)

    for obj in list:
        if(math.isnan(obj.pullrate) == False and obj.rate != 0):
            df = pd.concat([pd.DataFrame([[obj.machine, obj.id, obj.pullrate, obj.plies, obj.grade, 
                                           obj.scrapFactor, obj.quantity, obj.rate, obj.feetPerLog, 
                                           obj.rollPerLog, obj.sheetWidth]], columns=columnName), df], ignore_index=True)

    #df.to_csv("data.csv")

    return df


def Available(Foldername):
    list = []
    with open("C:\\Users\\ajone\\OneDrive\\Desktop\\HackathonPackageV2\\HackathonPackageV2\\DataCache\\OptimizerSituations\\" + Foldername + "\\initialPOs.json", 'r') as f:
        data = json.load(f)
    count = 0
    for field, attribute in data.items():
        if(field == "ProductionUnit"):
            for asset, machine in attribute.items():
                obj = Avail(asset, machine)
                list.append(obj)

        if(field == "ProcessOrder"):
            for asset, val in attribute.items():
                for obj in list:
                    if(obj.asset == asset):
                        obj.po = val

        if(field == "Prod_Id"):
            for asset, val in attribute.items():
                for obj in list:
                    if(obj.asset == asset):
                        obj.id = val

        if(field == "ForecastStartTime"):
            for asset, val in attribute.items():
                for obj in list:
                    if(obj.asset == asset):
                        obj.startIPO = val

        if(field == "ForecastEndTime"):
            for asset, val in attribute.items():
                for obj in list:
                    if(obj.asset == asset):
                        obj.endIPO = val
        
        if(field == "ForecastQuantity"):
            for asset, val in attribute.items():
                for obj in list:
                    if(obj.asset == asset):
                        obj.quantity = val

        if(field == "Grade"):
            for asset, val in attribute.items():
                for obj in list:
                    if(obj.asset == asset):
                        obj.grade = val

    f.close()


    with open("C:\\Users\\ajone\\OneDrive\\Desktop\\HackathonPackageV2\\HackathonPackageV2\\DataCache\\OptimizerSituations\\" + Foldername + "\\reservedTimes.json", 'r') as f:
        data = json.load(f)

        for field, attribute in data.items():
            if(field == "ProductionUnit"):
                for asset, machine in attribute.items():
                    obj = Avail(asset, machine)
                    list.append(obj)

            if(field == "ForecastStartTime"):
                for asset, val in attribute.items():
                    for obj in list:
                        if(obj.asset == asset):
                            obj.startReserve = val

            if(field == "ForecastEndTime"):
                for asset, val in attribute.items():
                    for obj in list:
                        if(obj.asset == asset):
                            obj.endReserve = val


    columnName = ["Machine", "ID", "Start of Initial PO", "End of Initial PO", "Process Order", "Grade", "Quantity", "Start of Reserve Time", "End of Reserve Time"]

    #pd.set_option('display.max_rows', None)

    df = pd.DataFrame(columns=columnName)

    for obj in list:
        df = pd.concat([pd.DataFrame([[obj.machine, obj.id, obj.startIPO, obj.endIPO, obj.po, obj.grade, obj.quantity, obj.startReserve, obj.endReserve]], columns=columnName), df], ignore_index=True)
    

    return df
    
