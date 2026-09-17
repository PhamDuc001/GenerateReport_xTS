import argparse
import json
import os
import re
import zipfile
import shutil
import subprocess
import sys
import threading
from datetime import datetime
import xml.etree.ElementTree as ET
from turtle import *

if os.name == 'nt':
    os.system('')

COLOR_RED = "\033[91m"
COLOR_RESET = "\033[0m"
FAIL_TAG = f"{COLOR_RED}fail{COLOR_RESET}"

failed_logs = []
checked_dirs = set()

def log_fail(*args, **kwargs):
    msg = " ".join(str(arg) for arg in args).rstrip()
    if not msg:
        return
    if msg.endswith(FAIL_TAG):
        formatted_msg = msg
    else:
        m = re.search(r'(?i)\bfail$', msg)
        if m:
            formatted_msg = msg[:m.start()] + FAIL_TAG
        else:
            formatted_msg = f"{msg} {FAIL_TAG}"
    print(formatted_msg, **kwargs)
    if formatted_msg not in failed_logs:
        failed_logs.append(formatted_msg)

def is_valid_result_name(name):
    return bool(re.match(r"^\d{4}\.\d{2}\.\d{2}_\d{2}\.\d{2}\.\d{2}", name))

def clean_invalid_results_items(results_dir):
    if not os.path.exists(results_dir) or not os.path.isdir(results_dir):
        return

    for item in os.listdir(results_dir):
        if item.startswith("."):
            continue
        item_path = os.path.join(results_dir, item)
        if os.path.isdir(item_path) or os.path.islink(item_path):
            if not is_valid_result_name(item):
                try:
                    if os.path.islink(item_path):
                        os.unlink(item_path)
                        print(f"Removed invalid symlink: {item_path}")
                    else:
                        shutil.rmtree(item_path)
                        print(f"Removed invalid folder: {item_path}")
                except Exception as e:
                    log_fail(f"Error removing invalid folder '{item}' in {results_dir}: {e}")

checked_logs_dirs = set()

def check_and_clean_logs_folder(logs_dir, context_label=""):
    if not os.path.exists(logs_dir) or not os.path.isdir(logs_dir):
        return

    logs_dir_norm = os.path.normpath(os.path.abspath(logs_dir))
    if logs_dir_norm in checked_logs_dirs:
        return
    checked_logs_dirs.add(logs_dir_norm)

    for item in os.listdir(logs_dir):
        if item.startswith("."):
            continue
        item_path = os.path.join(logs_dir, item)
        if os.path.isdir(item_path) or os.path.islink(item_path):
            if not is_valid_result_name(item):
                try:
                    if os.path.islink(item_path):
                        os.unlink(item_path)
                        print(f"Removed invalid symlink in logs: {item_path}")
                    else:
                        shutil.rmtree(item_path)
                        print(f"Removed invalid folder in logs: {item_path}")
                except Exception as e:
                    log_fail(f"[{context_label}] Error removing invalid folder '{item}' in logs: {e}")

    remaining_items = [it for it in os.listdir(logs_dir) if not it.startswith(".")]
    for item in remaining_items:
        item_path = os.path.join(logs_dir, item)
        if (os.path.isdir(item_path) or os.path.islink(item_path)) and not is_valid_result_name(item):
            log_fail(f"[{context_label}] Folder in logs/ does not match format YYYY.MM.DD_HH.MM.SS: '{item}'")

def clean_all_logs_in_base_path(base_path):
    if not os.path.exists(base_path) or not os.path.isdir(base_path):
        return
    for root, dirs, _ in os.walk(base_path):
        if "logs" in dirs:
            logs_dir = os.path.join(root, "logs")
            rel = os.path.relpath(logs_dir, base_path).replace("\\", "/")
            check_and_clean_logs_folder(logs_dir, rel)

def check_folder_zip_pairs(target_dir, context_label=""):
    if not os.path.exists(target_dir) or not os.path.isdir(target_dir):
        return

    target_dir_norm = os.path.normpath(os.path.abspath(target_dir))
    if target_dir_norm in checked_dirs:
        return
    checked_dirs.add(target_dir_norm)

    if "results" in context_label.lower():
        clean_invalid_results_items(target_dir)

    items = [it for it in os.listdir(target_dir) if not it.startswith(".")]

    subfolders = set()
    zip_stems = {}

    for item in items:
        item_path = os.path.join(target_dir, item)
        if os.path.isdir(item_path):
            subfolders.add(item)
        elif os.path.isfile(item_path) and item.lower().endswith(".zip"):
            stem = item[:-4]
            zip_stems[stem] = item

    if not subfolders and not zip_stems:
        log_fail(f"[{context_label}] Empty directory (no test result folders or zip files): {target_dir}")
        return

    missing_zip = sorted(subfolders - set(zip_stems.keys()))
    for fol in missing_zip:
        log_fail(f"[{context_label}] Folder '{fol}' is missing zip file: '{fol}.zip'")

    missing_folder = sorted(set(zip_stems.keys()) - subfolders)
    for stem in missing_folder:
        actual_zip = zip_stems[stem]
        log_fail(f"[{context_label}] Zip file '{actual_zip}' is missing folder: '{stem}'")

checked_results_logs_pairs = set()

def check_results_logs_matching(results_dir, logs_dir, context_label=""):
    if not os.path.exists(results_dir) or not os.path.isdir(results_dir):
        return

    pair_key = (os.path.normpath(os.path.abspath(results_dir)), os.path.normpath(os.path.abspath(logs_dir)))
    if pair_key in checked_results_logs_pairs:
        return
    checked_results_logs_pairs.add(pair_key)

    clean_invalid_results_items(results_dir)
    check_and_clean_logs_folder(logs_dir, f"{context_label}/logs")

    if not os.path.exists(logs_dir) or not os.path.isdir(logs_dir):
        log_fail(f"[{context_label}] Missing corresponding logs directory: {logs_dir}")
        return

    result_folders = {
        item for item in os.listdir(results_dir)
        if not item.startswith(".")
        and os.path.isdir(os.path.join(results_dir, item))
        and is_valid_result_name(item)
    }

    log_folders = {
        item for item in os.listdir(logs_dir)
        if not item.startswith(".")
        and os.path.isdir(os.path.join(logs_dir, item))
        and is_valid_result_name(item)
    }

    missing_in_logs = sorted(result_folders - log_folders)
    for fol in missing_in_logs:
        log_fail(f"[{context_label}] Session folder '{fol}' in results/ is missing in logs/")

    missing_in_results = sorted(log_folders - result_folders)
    for fol in missing_in_results:
        log_fail(f"[{context_label}] Session folder '{fol}' in logs/ is missing in results/")

def run_command(command):
    process = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    process.wait()
    output, error = process.communicate()
    if not error is None:
        for line in error.decode("utf-8").split("\n"):
            if line.strip():
                log_fail(line)
    if not output is None:
        for ot in output.decode("utf-8").split("\n"):
            print(ot)
    return output.decode("utf-8")
def MakeNewFolder(path, newName):
    try:
        os.mkdir(os.path.join(path, newName))
    except FileExistsError:
        print("Folder ", newName, " exists")
    return path + "/" + newName


def unzip_file(path_to_file, des):
    try:
        shutil.unpack_archive(path_to_file, des, format="zip")
    except Exception as e:
        log_fail("Error ", e)


def CopyAndRenameHtml(srcPath, desPath, name):
    try:
        shutil.copy2(srcPath, desPath + "/" + name + ".html")
        print("Copy " + name + ".html file success")
    except FileNotFoundError:
        log_fail("Source file " + srcPath + " not found")


def CopyAndRenameXml(srcPath, desPath, name):
    try:
        shutil.copy2(srcPath, desPath + "/" + name + ".xml")
        print("Copy " + name + ".xml file success")
    except FileNotFoundError:
        log_fail("Source file " + srcPath + " not found")

def zip_folder(folder_path, zip_path):
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(folder_path):
            for file in files:
                full_path = os.path.join(root, file)
                rel_path = os.path.relpath(full_path, folder_path)
                zipf.write(full_path, rel_path)

def CopyFile(srcPath, desPath):
    try:
        shutil.copy2(srcPath, desPath)
        print("Copy " + srcPath + " file success")
    except FileNotFoundError:
        log_fail("Source file " + srcPath + " not found")


def CopyFolder(srcFolder, desFolder, name):
    try:
        shutil.copytree(srcFolder, desFolder + "/" + name, copy_function=shutil.copy2)
        print("Copy " + name + " folder success")
    except Exception as e:
        log_fail("Source file " + srcFolder + " not found :", e)


# Struct = []
class GenerDict():
    def __init__(self):
        self.path = None
        self.strc = {}

    def structs(self, path):
        self.path = path
        for fol in os.listdir(self.path):
            tempPath = os.path.join(self.path, fol)
            if not os.path.isfile(tempPath):
                if "CTS_Verifier" in str(fol):
                    self.strc[str(fol)] = {}
                    check_folder_zip_pairs(tempPath, "CTS_Verifier")
                    continue
                self.strc[str(fol)] = {}
                # For in XTS folder
                for child in os.listdir(tempPath):
                    if str(child) == "results" and os.path.isdir(os.path.join(tempPath, child)):
                        results_path = os.path.join(tempPath, child)
                        logs_path = os.path.join(tempPath, "logs")
                        check_folder_zip_pairs(results_path, f"{fol}/results")
                        check_results_logs_matching(results_path, logs_path, str(fol))
                        self.strc[str(fol)]["Multiple"] = {}
                        lastTestMulti = lastTestResult()
                        lastest = lastTestMulti.getLastTestFolder(results_path)
                        if lastest != "0":
                            self.strc[str(fol)]["Multiple"]['xml'] = str(
                                results_path + "/" + lastest + "/test_result.xml")
                            self.strc[str(fol)]["Multiple"]['html'] = str(
                                results_path + "/" + lastest + "/test_result.html")
                            self.strc[str(fol)]["Multiple"]['zip'] = str(
                                results_path + "/" + lastest + ".zip")
                            self.strc[str(fol)]["Multiple"]['folder'] = str(
                                results_path + "/" + lastest)
                            self.strc[str(fol)]["Multiple"]['name'] = str(lastest)
                    elif str(child) == "logs" and os.path.isdir(os.path.join(tempPath, child)):
                        logs_path = os.path.join(tempPath, child)
                        check_and_clean_logs_folder(logs_path, f"{fol}/logs")
                    elif str(child) == "single" and os.path.isdir(os.path.join(tempPath, child)):
                        temp1 = os.path.join(tempPath, child)
                        # For in siggle Module XTS folder
                        for sg in os.listdir(temp1):
                            temp2 = os.path.join(temp1, sg)
                            if not os.path.isfile(temp2):
                                self.strc[str(fol)][str(sg)] = {}
                                moduleNAme = sg
                                # For in Result of single Module XTS folder
                                for child2 in os.listdir(temp2):
                                    if str(child2) == "results" and os.path.isdir(os.path.join(temp2, child2)):
                                        single_results = os.path.join(temp2, child2)
                                        single_logs = os.path.join(temp2, "logs")
                                        check_folder_zip_pairs(single_results, f"{fol}/single/{sg}/results")
                                        check_results_logs_matching(single_results, single_logs, f"{fol}/single/{sg}")
                                        lastTest = lastTestResult()
                                        lastTestFol = lastTest.getLastTestFolder(single_results)
                                        if lastTestFol != "0":
                                            self.strc[str(fol)][str(sg)]['xml'] = str(
                                                single_results + "/" + lastTestFol + "/test_result.xml")
                                            self.strc[str(fol)][str(sg)]['html'] = str(
                                                single_results + "/" + lastTestFol + "/test_result.html")
                                            self.strc[str(fol)][str(sg)]['zip'] = str(
                                                single_results + "/" + lastTestFol + ".zip")
                                            self.strc[str(fol)][str(sg)]['folder'] = str(
                                                single_results + "/" + lastTestFol)
                                            self.strc[str(fol)][str(sg)]['name'] = str(lastTestFol)
                                    elif str(child2) == "logs" and os.path.isdir(os.path.join(temp2, child2)):
                                        single_logs = os.path.join(temp2, child2)
                                        check_and_clean_logs_folder(single_logs, f"{fol}/single/{sg}/logs")
                    # shutil.make_archive(base_name=path+"/01."+fol, format='zip', root_dir=path,base_dir=fol)
            elif os.path.isfile(tempPath) and str(tempPath).__contains__("Verifier"):
                #make temp folder to unzip Verifier file
                MakeNewFolder(self.path, "Verifier")
                template = str(os.path.join(self.path, "Verifier"))
                unzip_file(tempPath, template)
                for temp_path in os.listdir(template):
                    temp_dir = str(os.path.join(template,temp_path))
                    if os.path.isfile(temp_dir) and str(temp_dir).__contains__("zip"):
                        if str(temp_dir).__contains__("cts")or str(temp_dir).__contains__("CTS"):
                            MakeNewFolder(self.path, "CTS_Verifier")
                            cts_ver_fol = str(os.path.join(self.path, "CTS_Verifier"))
                            self.strc["CTS_Verifier"]={}
                            self.strc["CTS_Verifier"]["ctsver_result_fol"] = cts_ver_fol
                            unzip_file(temp_dir, cts_ver_fol)
                            check_folder_zip_pairs(cts_ver_fol, "CTS_Verifier")
                    elif os.path.isdir(temp_dir):
                        if str(temp_dir).__contains__("ctsve"):
                            MakeNewFolder(self.path, "CTS_Verifier")
                            cts_ver_fol = str(os.path.join(self.path,"CTS_Verifier"))
                            run_command("cp -r "+temp_dir+"/* "+cts_ver_fol)
                            self.strc["CTS_Verifier"] = {}
                            self.strc["CTS_Verifier"]["ctsver_result_fol"]=cts_ver_fol
                            check_folder_zip_pairs(cts_ver_fol, "CTS_Verifier")
                shutil.rmtree(template)
        return self.strc


class lastTestResult():
    def __init__(self):
        self.fol_name = None
        self.datetime_oj = None
        self.sorted_fol = None
        self.masterPath = None
        self.folder_unsort = None

    def get_datetime_folder_name(self, fol_name):
        self.fol_name = fol_name
        try:
            parts = self.fol_name.split("_")
            if len(parts) >= 2:
                main_part = parts[0] + "_" + ".".join(parts[1].split(".")[:3])
                self.datetime_oj = datetime.strptime(main_part, "%Y.%m.%d_%H.%M.%S")
            else:
                self.datetime_oj = datetime.min
        except Exception as e:
            log_fail("Datetime parse error:", e)
            self.datetime_oj = datetime.min
        return self.datetime_oj
            
    def sortFolder(self, path):
        self.masterPath = path
        clean_invalid_results_items(path)
        self.folder_unsort = [
            folder for folder in os.listdir(path)
            if os.path.isdir(os.path.join(path, folder)) and is_valid_result_name(folder)
        ]
        self.sorted_fol = sorted(self.folder_unsort, key=self.get_datetime_folder_name)
        return self.sorted_fol

    def getLastTestFolder(self, path):
        if len(os.listdir(path)) > 0:
            return self.sortFolder(path)[len(self.sorted_fol) - 1]
        else:
            log_fail("Folder " + path + " empty")
            return "0"

def MakeInternal(path, struct):
    InternalPATH = path
    InternalStr = {}
    dict = struct
    script_directory = os.path.dirname(os.path.abspath(sys.argv[0]))
    templateFile = script_directory + "/TemplateInternal"
    templateFile = replacePath(templateFile)
    if dict.get("CTS") or dict.get("ATS") or dict.get("VTS") or dict.get("STS"):
        if dict.get("CTS"):
            path_to_firtXML = list(list(dict["CTS"].values())[0].values())[0]
        elif dict.get("ATS"):
            path_to_firtXML = list(list(dict["ATS"].values())[0].values())[0]
        elif dict.get("VTS"):
            path_to_firtXML = list(list(dict["VTS"].values())[0].values())[0]
        elif dict.get("STS"):
            path_to_firtXML = list(list(dict["STS"].values())[0].values())[0]
    overview = GetOverview(path_to_firtXML)
    for i in dict:
        overview = GetOverview(path_to_firtXML)
        MakeNewFolder(InternalPATH, i + "Results")
        tempP = InternalPATH + "/" + i + "Results" + "/DataforAuto"
        InternalStr[i] = {}
        InternalStr[i]["path"] = str(InternalPATH) + "/" + str(i) + "Results"
        InternalStr[i]["data"] = str(tempP)
        for k in os.listdir(str(templateFile)):
            try:
                shutil.copy2(str(templateFile + "/" + k), InternalStr[i]["path"])
            except FileNotFoundError:
                log_fail("Source file " + k + " not found")
        print("Finish copy template file html")
        for j in dict[i]:
            try:
                if dict[i][j]["html"] != None and dict[i][j]["xml"] != None:
                    if j == "Multiple":
                        CopyAndRenameHtml(dict[i][j]["html"], InternalStr[i]["path"], "00." + i)
                    #  CopyAndRenameXml(dict[i][j]["xml"], InternalStr[i]["data"], "00." + i)
                    else:
                        CopyAndRenameHtml(dict[i][j]["html"], InternalStr[i]["path"], j)
                    # CopyAndRenameXml(dict[i][j]["xml"], InternalStr[i]["data"], j)
            except KeyError as e:
                log_fail(f"KeyError in MakeInternal HTML ({i}/{j}):", e)
        print("Finish creating " + i + " folder")
        file = open(script_directory + "/name_report_rules.json")      
        data = json.load(file)
        model = overview["model"]
        if model in ["aivi2_n_full", "aivi2e_high", "aivi2e_std"]:
           overview["model"] = data[model]
        elif overview["brand"] == "ACCESS" or overview["brand"] == "RENAULT":
           overview["model"] = data[model] + overview["DPI"] + "DPI"
        nameReport = "02.LGE_" + overview["model"] + "_" + i + "_Result_" + overview["sw_ver"]
        thu_muc = InternalStr[i]["path"]
        ten_nen = InternalPATH + "/" + nameReport  # archive file name
        try:
            shutil.make_archive(ten_nen, 'zip', thu_muc)
        except Exception as e:
            log_fail("Fail zip:", e)
        MakeNewFolder(str(InternalStr[i]["path"]), "DataforAuto")
        for j in dict[i]:
            try:
                if dict[i][j]["html"] != None and dict[i][j]["xml"] != None:
                    if j == "Multiple":
                        # CopyAndRenameHtml(dict[i][j]["html"], InternalStr[i]["path"], "00." + i)
                        CopyAndRenameXml(dict[i][j]["xml"], InternalStr[i]["data"], "00." + i)
                    else:
                        # CopyAndRenameHtml(dict[i][j]["html"], InternalStr[i]["path"], j)
                        CopyAndRenameXml(dict[i][j]["xml"], InternalStr[i]["data"], j)
            except KeyError as e:
                log_fail(f"KeyError in MakeInternal XML ({i}/{j}):", e)
    return InternalStr


def MakeOemApfe(path, struct):
    InternalPATH = path
    InternalStr = {}
    dict = struct
    for i in dict:
        InternalStr[i] = {}
        for j in dict[i]:
            try:
                if j == "Multiple":
                    MakeNewFolder(InternalPATH, i)
                    InternalStr[i]['Multiple'] = InternalPATH + "/" + i + "/" + "00." + i
                    MakeNewFolder(InternalPATH + "/" + i, "00." + i)
                    if 'folder' in dict[i][j] and os.path.exists(dict[i][j]['folder']):
                        CopyFolder(dict[i][j]['folder'], InternalStr[i]['Multiple'], dict[i][j]['name'])
                    if 'zip' in dict[i][j] and os.path.exists(dict[i][j]['zip']):
                        CopyFile(dict[i][j]['zip'], InternalStr[i]['Multiple'])
                else:
                    MakeNewFolder(InternalPATH, i)
                    InternalStr[i][j] = InternalPATH + "/" + i + "/" + j
                    MakeNewFolder(InternalPATH + "/" + i, j)
                    if 'folder' in dict[i][j] and os.path.exists(dict[i][j]['folder']):
                        CopyFolder(dict[i][j]['folder'], InternalStr[i][j], dict[i][j]['name'])
                    if 'zip' in dict[i][j] and os.path.exists(dict[i][j]['zip']):
                        CopyFile(dict[i][j]['zip'], InternalStr[i][j])
            except KeyError as e:
                log_fail(f"KeyError in MakeOemApfe ({i}/{j}):", e)
        print("Finish creating " + i + " folder")    
    try:
        src_cts = os.path.join(agruments(), "CTS_Verifier")
        if os.path.exists(src_cts):
            check_folder_zip_pairs(src_cts, "CTS_Verifier")
            CopyFolder(src_cts, InternalPATH, "CTS_Verifier")
            print("Copied CTS_Verifier Ok")
    except Exception as e:
        log_fail("CTS_Verifier copy error:", e)
    
    return InternalStr

def MakeOemApfeUpload(path, struct):
    InternalPATH = path
    InternalStr = {}
    dict = struct
    
    for i in dict:
        InternalStr[i] = {}
        
        for j in dict[i]:
            try:
                if j == "Multiple":
                    MakeNewFolder(InternalPATH, i)
                    InternalStr[i]['Multiple'] = InternalPATH + "/" + i              
                    if 'zip' in dict[i][j] and os.path.exists(dict[i][j]['zip']):
                        CopyFile(dict[i][j]['zip'], InternalStr[i]['Multiple'] + "/" + dict[i][j]['zip'].split("/")[-1])
                else:
                    MakeNewFolder(InternalPATH, i)
                    InternalStr[i][j] = InternalPATH + "/" + i 
                    if 'zip' in dict[i][j] and os.path.exists(dict[i][j]['zip']):
                        CopyFile(dict[i][j]['zip'], InternalStr[i][j] + "/" + dict[i][j]['zip'].split("/")[-1])
            except KeyError as e:
                log_fail(f"KeyError in MakeOemApfeUpload ({i}/{j}):", e)
        
        print("Finish creating " + i + " folder")
    
    try:
        src_cts = os.path.join(agruments(), "CTS_Verifier")
        dst_cts = os.path.join(InternalPATH, "CTS_Verifier")

        if os.path.exists(src_cts):
            os.makedirs(dst_cts, exist_ok=True)

            for file in os.listdir(src_cts):
                if file.endswith(".zip"):
                    src_file = os.path.join(src_cts, file)
                    dst_file = os.path.join(dst_cts, file)

                    shutil.copy2(src_file, dst_file)
        else:
            log_fail("CTS_Verifier not found")

    except Exception as e:
            log_fail("CTS_Verifier copy error:", e)
  
    return InternalStr
    
def restore_xts_folders(base_path):

    # Remove all 01.xxx.zip files
    for item in os.listdir(base_path):

        full_path = os.path.join(base_path, item)

        if os.path.isfile(full_path) and item.startswith("01.") and item.endswith(".zip"):
            try:
                os.remove(full_path)
                print("Remove", item)
            except Exception as e:
                log_fail("Restore remove zip error:", e)
    print("=== CLEAN DONE ===")	
    # Rename folder 01.xxx -> xxx
    for item in os.listdir(base_path):

        full_path = os.path.join(base_path, item)

        if not os.path.isdir(full_path):
            continue

        if not item.startswith("01."):
            continue

        original_name = item[3:]

        try:
            os.rename(
                full_path,
                os.path.join(base_path, original_name)
            )
            print(f"Restore {item} -> {original_name}")
        except Exception as e:
            log_fail("Restore rename folder error:", e)

    clean_all_logs_in_base_path(base_path)
                     
def rename_and_zip_xts_folders(base_path):
    print("===============================================================================================")
    if failed_logs:
        print("!!!!!!!!!!!!!!!!!!!!!!!! FAILED LOGS SUMMARY !!!!!!!!!!!!!!!!!!!!!!!!")
        print(f"Total failed logs detected: {len(failed_logs)}")
        for idx, log in enumerate(failed_logs, 1):
            print(f"  [{idx}] {log}")
        print("===============================================================================================")
    else:
        print("No failed logs detected.")
        print("===============================================================================================")

    while True:
       answer = input(f"Do you want to rename + zip folders in:{base_path}\n(Y/N): ").strip().lower()

       if answer == "y":
          break
       elif answer == "n":
          print("Skip rename + zip folder ==> DONE.")
          return
       else:
          print("Please enter Y or N")

    for item in os.listdir(base_path):

        full_path = os.path.join(base_path, item)

        if not os.path.isdir(full_path):
            continue

        if item.startswith("01."):
            continue

        new_name = f"01.{item}"
        new_path = os.path.join(base_path, new_name)

        try:
            os.rename(full_path, new_path)

            shutil.make_archive(
                base_name=new_path,
                format="zip",
                root_dir=base_path,
                base_dir=new_name
            )

            print(f"Rename {item} -> {new_name}")
            print(f"Create {new_name}.zip")

        except Exception as e:
            log_fail("Rename and zip error:", e)     

def cleanup_output(master_path):
    print("=== CLEANUP OLD DATA ===")

    for item in os.listdir(master_path):
        full_path = os.path.join(master_path, item)

        if item == "01.Full":
            continue

        try:
            # Delete folder
            if os.path.isdir(full_path):
                shutil.rmtree(full_path)
                print("Deleted folder:", full_path)

            # Delete file
            elif os.path.isfile(full_path):
                os.remove(full_path)
                print("Deleted file:", full_path)

        except Exception as e:
            log_fail("Cleanup error:", full_path, e)               
                   
class thread(threading.Thread):
    def __init__(self, thread_name, thread_ID, path_to_folder, parent_folder):
        threading.Thread.__init__(self)
        self.thread_name = thread_name
        self.thread_ID = thread_ID
        self.base_file = path_to_folder
        self.path_parent_folder = parent_folder
        # helper function to execute the threads

    def run(self):
        try:
            shutil.make_archive(base_name=self.base_file, format="zip", root_dir=self.path_parent_folder)
            print("Compress ", self.base_file, " folder")
        except Exception as e:
            log_fail("Thread compress error:", e)


def replacePath(path):
    newPath = str(path).replace("\\", "/")
    return newPath.replace("//", "/")


def MakeReportStruct(dict):
    path = agruments()
    MasterFol = str(path)[:len(path) - 8]
    # for i in range(4):
    #     dict[i]={}
    dict[0] = str(os.path.join(MasterFol, "00.Internal"))
    dict[1] = str(os.path.join(MasterFol, "00.OEM_APFE"))
    dict[2] = str(os.path.join(MasterFol, "00.OEM_APFE_UPLOAD"))
    # dict[3] = str(os.path.join(MasterFol, "00.Report"))
    print(1)
    for i in dict.values():
        try:
            os.mkdir(i)
            print("Create ", i)
        except FileExistsError:
            print("Folder exists")
    print("Created Report Struct")
    return dict


def agruments():
    parser = argparse.ArgumentParser(description='parse an XML file')
    parser.add_argument('-p', '--path', help='Path to parent of 01.FULL Folder')
    args = parser.parse_args()
    newPath = str(args.path).replace("\\", "/")
    return newPath.replace("//", "/")


def GetOverview(path):
    xmltree = ET.parse(path)
    overview = {}
    overview["model"] = str(xmltree.find("Build").get("build_device"))
    overview["brand"] = str(xmltree.find("Build").get("build_brand")).upper()
    overview["sw_ver"] = str(xmltree.find("Build").get("build_version_incremental"))[:12]
    if not overview["brand"] == "NISSAN": 
    	if overview["model"] == "aivi2_r_da_aub": 
    	   dpi = str(xmltree.find("Build").get("build_product")).split("-")     
    	   overview["DPI"] = dpi[len(dpi) - 1]
    	else:
    	   dpi = str(xmltree.find("Build").get("build_product")).split("-")    	
    	   overview["DPI"] = dpi[len(dpi) - 2]
    return overview


if __name__ == '__main__':
    print("""ooooo      ooo           oooooooooo.            
`888b.     `8'           `888'   `Y8b           
 8 `88b.    8   .oooo.    888     888  .ooooo.  
 8   `88b.  8  `P  )88b   888oooo888' d88' `88b 
 8     `88b.8   .oP"888   888    `88b 888   888 
 8       `888  d8(  888   888    .88P 888   888 
o8o        `8  `Y888""8o o888bood8P'  `Y8bod8P' 
                                                
                                                
                                                
""")
    print("""  #####    ######   ##  ##   ######   #####             #####    ######   #####     ####    #####   ####### 
 ### ###   ##       ##  ##   ##       ##  ##            ##  ##   ##       ##  ##   ##  ##   ##  ##     ##   
 ###       ##       ### ##   ##       ##  ##            ##  ##   ##       ##  ##   ##  ##   ##  ##     ##   
 ## ####  ######   #### ##  ######   ######            ######   ######   ######   #    ##  ######     ##    
 ##    #  ##       ## ###   ##       ####              ####     ##       ##       ##  ##   ####       ##    
 ##   #   ##       ##  ##   ##       ## ##             ## ##    ##       ##       ##  ##   ## ##      ##    
  ####    #####    ##  ##   #####    ##  ###           ##  ###  #####    ##        ####    ##  ###    ## Version V1.3   
                                                                                                            
""")
    path = agruments()
    MasterFol = str(path)[:len(path) - 8]
    cleanup_output(MasterFol)
    restore_xts_folders(agruments())
    StructReport = {}
    StructResult = {}
    StructReport = MakeReportStruct(StructReport)
    Gender = GenerDict()
    StructResult = Gender.structs(agruments())
    MakeOemApfe(StructReport[1], StructResult)  
    MakeOemApfeUpload(StructReport[2], StructResult) 
    zip_folder(StructReport[1], StructReport[1] + ".zip")
    zip_folder(StructReport[2], StructReport[2] + ".zip")
    try:
        StructResult.pop("CTS_Verifier")
    except Exception as e:
        print("CTS Verifier folder not exist")
    MakeInternal(StructReport[0], StructResult)
    rename_and_zip_xts_folders(agruments())
# # Version 1.5_18062026

