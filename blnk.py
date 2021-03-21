#!/usr/bin/env python
import sys
import os
import platform
import subprocess

profile = None

myDirName = "blnk"
AppDatas = None
local = None
myLocal = None
shortcutsDir = None
if platform.system() == "Windows":
    profile = os.environ.get("USERPROFILE")
    tmp = os.path.join(profile, "AppData")
    AppDatas = os.path.join(tmp, "Roaming")
    local = os.path.join(tmp, "Local")
    share = local
    myShare = os.path.join(local, myDirName)
    shortcutsDir = os.path.join(profile, "Desktop")
    dtPath = os.path.join(shortcutsDir, "blnk.blnk")
else:
    profile = os.environ.get("HOME")
    AppDatas = os.path.join(profile, ".config")
    local = os.path.join(profile, ".local")
    share = os.path.join(local, "share")
    myShare = os.path.join(share, "blnk")
    shortcutsDir = os.path.join(share, "applications")
    dtPath = os.path.join(shortcutsDir, "blnk.desktop")


class BLink:
    NO_SECTION = "\n"

    def __init__(self, path, assignmentOperator=":",
                 commentDelimiter="#"):
        self.contentType = None
        self.tree = {}
        self.lastSection = None
        self.path = None
        self.assignmentOperator = assignmentOperator
        self.commentDelimiter = commentDelimiter
        self.load(path)

    def splitLine(self, line):
        i = line.find(self.assignmentOperator)
        if i < 0:
            raise ValueError("The line contains no '{}': `{}`"
                             "".format(self.assignmentOperator,
                                       line))
        ls = line.strip()
        if self.isComment(ls):
            raise ValueError("splitLine doesn't work on comments.")
        if self.isSection(ls):
            raise ValueError("splitLine doesn't work on sections.")
        k = line[:i].strip()
        v = line[i+len(self.assignmentOperator):].strip()
        if self.commentDelimiter in v:
            print("WARNING: `{}` contains a comment delimiter '{}'"
                  " but inline comments are not supported."
                  "".format(line, self.commentDelimiter))
        return (k, v)

    def getSection(self, line):
        ls = line.strip()
        if ((len(ls) >= 2) and ls.startswith('[') and ls.endswith(']')):
            return ls[1:-1].strip()
        return None

    def isSection(self, line):
        return self.getSection(line) is not None

    def isComment(self, line):
        return line.strip().startswith(self.commentDelimiter)

    def _pushLine(self, line, row=None, col=None):
        '''
        Keyword arguments
        row -- Show this row (such as line_index+1) in syntax messages.
        col -- Show this col (such as char_index+1) in syntax messages.
        '''
        if row is None:
            if self.lastSection is not None:
                print("WARNING: The line `{}` was a custom line not on"
                      " a row of a file, but it will be placed in the"
                      " \"{}\" section which was still present."
                      "".format(line, self.lastSection))
        if self.contentType is None:
            if not line.startswith("Content-Type:"):
                raise ValueError(
                    "The file must contain \"Content-Type:\""
                    " (usually \"Content-Type: text/blnk\")"
                    " before anything else, but"
                    " _pushLine got \"{}\" (last file: {})"
                    "".format(line, self.path))
        trySection = self.getSection(line)
        if self.isComment(line):
            pass
        elif trySection is not None:
            section = trySection
            if len(section) < 1:
                pre = ""
                if lineN is not None:
                    if self.path is not None:
                        pre = self.path + ":"
                        if row is not None:
                            pre += str(row) + ":"
                            if col is not None:
                                pre += str(col) + ":"
                if len(pre) > 0:
                    pre += " "
                raise ValueError(pre+"_pushLine got an empty section")
            else:
                self.lastSection = section
        else:
            k, v = self.splitLine(line)
            if k == "Content-Type":
                self.contentType = v
                return
            section = self.lastSection
            if section is None:
                section = BLink.NO_SECTION
            sectionD = self.tree.get(section)
            if sectionD is None:
                sectionD = {}
                self.tree[section] = sectionD
            sectionD[k] = v

    def load(self, path):
        self.path = path
        with open(path, 'r') as ins:
            row = 0
            for line in ins:
                row += 1
                self._pushLine(line, row=row)
            self.lastSection = None

    def getBranch(self, section, key):
        '''
        Get a tuple containing the section (section name key for
        self.tree) and the value self.tree[section][key]. The reason
        section is returned is in case the key doesn't exist there but
        exists in another section.
        '''
        v = None
        sectionD = self.tree.get(section)
        if sectionD is not None:
            v = sectionD.get(key)
        if v is None:
            section = None
            for trySection, sectionD in self.tree.keys():
                v = sectionD.get(key)
                if v is not None:
                    section = trySection
                    break
        return section, v

    def getExec(self):
        result = None
        trySection = BLink.NO_SECTION
        key = "Exec"
        section, v = self.getBranch(trySection, key)
        if v is None:
            path = self.path
            if path is not None:
                path = "\"" + path + "\""
            print("WARNING: There was no \"{}\" variable in {}"
                  "".format(key, path))
            return False
        elif section != trySection:
            sectionMsg = section
            if section == BLink.NO_SECTION:
                sectionMsg = "the main section"
            else:
                sectionMsg = "[{}]".format(section)
            print("WARNING: \"{}\" was in {}".format(key, sectionMsg))
        if v is None:
            return None
        path = v
        if v[1:2] == ":":
            if v[2:3] != "\\":
                raise ValueError(
                    "The third character should be '\\' when the"
                    " 2nd character is ':', but the Exec value was"
                    " \"{}\"".format(v)
                )
            if platform.system() != "Windows":
                path = v[3:].replace("\\", "/")
                if "%USERPROFILE%" in path:
                    path = path.replace("%USERPROFILE%", profile)
                else:
                    if path.lower().startswith("users/"):
                        parts = path.split("/")
                        # print("parts={}".format(parts))
                        rel = os.path.join(*parts[2:])
                        old = os.path.join(*parts[:2])
                        print("* changing \"{}\" to \"{}\""
                              "".format(old, profile))
                        # ^ splat ('*') since join takes multiple
                        #   params not a list.
                        foundCloud = "owncloud/"
                        cloud = os.path.join(profile, "Nextcloud")
                        # cloud = os.path.join(profile, "ownCloud")
                        if (rel.lower().startswith(foundCloud)
                                and os.path.isdir(cloud)):
                            path = os.path.join(
                                cloud,
                                rel[len(foundCloud):],
                            )
                            print("* changed \"{}\" to \"{}\""
                                  "".format(os.path.join(*parts[:2]),
                                            cloud))
                        else:
                            path = os.path.join(profile, rel)

        return path

    def run(self):
        execStr = self.getExec()
        print("* running \"{}\"...".format(execStr))
        runner = subprocess.check_call
        if hasattr(subprocess, 'run'):
            runner = subprocess.check_call
            print("  - using subprocess.check_call")
        tryCmd = "xdg-open"
        # TODO: try os.popen('open "{}"') on mac
        if platform.system() == "Windows":
            os.startfile(execStr, 'open')
            # runner('cmd /c start "{}"'.format(execStr))
            return
        try:
            print("  - {}...".format(tryCmd))
            runner([tryCmd, execStr])
        except OSError as ex:
            try:
                print("  - open...")
                runner(['open', execStr], check=True)
            except OSError as ex:
                print("  - trying xdg-launch...")
                runner(['xdg-launch', execStr], check=True)

dtLines = {
    "[Desktop Entry]",
    "Exec=blnk",
    "MimeType=text/blnk;",
    "Name=blnk",
    "NoDisplay=true",
    "Type=Application",
}

def main(args):
    print("* checking for \"{}\"".format(dtPath))
    if not os.path.isfile(dtPath):
        print("* writing \"{}\"...".format(dtPath))
        with open(dtPath, 'w') as outs:
            for line in dtLines:
                outs.write(line + "\n")
        print("  OK")

    if len(args) < 2:
        raise ValueError("The first argument is the program but there"
                         " is no argument after that. Provide a file.")
    link = BLink(args[1])
    link.run()

if __name__ == "__main__":
    main(sys.argv)
