#!/usr/bin/env python

# Copyright 2015 Samsung Electronics Co., Ltd.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
#  This file converts src/js/iotjs.js to a C-array in include/iotjs_js.h file

import sys
import glob
import os
import re
import subprocess

from common.system.filesystem import FileSystem as fs


def extractName(path):
    return fs.splitext(os.path.basename(path))[0]


def writeLine(fo, content, indent=0):
    buf = '  ' * indent
    buf += content
    buf += '\n'
    fo.write(buf)


def regroup(l, n):
    return [l[i:i+n] for i in range(0, len(l), n)]


def removeComments(code):
    pattern = r'(\".*?\"|\'.*?\')|(/\*.*?\*/|//[^\r\n]*$)'
    regex = re.compile(pattern, re.MULTILINE | re.DOTALL)

    def _replacer(match):
        if match.group(2) is not None:
            return ""
        else:
            return match.group(1)

    return regex.sub(_replacer, code)


def removeWhitespaces(code):
    return re.sub('\n+', '\n', re.sub('\n +', '\n', code))


LICENSE = '''/* Copyright 2015 Samsung Electronics Co., Ltd.
 *
 * Licensed under the Apache License, Version 2.0 (the \"License\");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an \"AS IS\" BASIS
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 *
 * This file is generated by tools/js2c.py
 * Do not modify this.
 */
'''

HEADER1 = '''#ifndef IOTJS_JS_H
#define IOTJS_JS_H
namespace iotjs {
'''

FOOTER1 = '''}
#endif
'''

HEADER2 = '''#include <stdio.h>
#include "iotjs_js.h"
namespace iotjs {
'''

FOOTER2 = '''}
'''

SRC_PATH = '../src/'
JS_PATH = SRC_PATH + 'js/'
DUMPER = ""

# argument processing
buildtype = 'debug'
no_snapshot = False
if len(sys.argv) >= 2:
    buildtype = sys.argv[1]
    no_snapshot = True if sys.argv[2] == 'no_snapshot' else False
    DUMPER = sys.argv[3]

fout_h = open(SRC_PATH + 'iotjs_js.h', 'w')
fout_cpp = open(SRC_PATH + 'iotjs_js.cpp', 'w')
fout_h.write(LICENSE)
fout_h.write(HEADER1)
fout_cpp.write(LICENSE)
fout_cpp.write(HEADER2)

files = glob.glob(JS_PATH + '*.js')
for path in files:
    name = extractName(path)
    fout_cpp.write('const char ' + name + '_n[] = "' + name + '";\n')
    fout_h.write('extern const char ' + name + '_n[];\n')
    fout_h.write('extern const int ' + name + '_l;\n')
    if no_snapshot is True:
        fout_h.write('extern const char ' + name + '_s[];\n')
        fout_cpp.write('const char ' + name + '_s[] = {\n')
        code = open(path, 'r').read() + '\0'

        # minimize code when release mode
        if buildtype != 'debug':
            code = removeComments(code)
            code = removeWhitespaces(code)

        for line in regroup(code, 10):
            buf = ', '.join(map(lambda ch: str(ord(ch)), line))
            if line[-1] != '\0':
                buf += ','
            writeLine(fout_cpp, buf, 1)

        writeLine(fout_cpp, '};')
        writeLine(fout_cpp,
                  'const int ' + name + '_l = ' + str(len(code)-1) + ';')

    else:
        fout_h.write('extern const unsigned char ' + name + '_s[];\n')
        fout_cpp.write('const unsigned char ' + name + '_s[] = {\n')

        fmodule = open(path, 'r')
        module = fmodule.read()
        fmodule.close()

        fmodule_wrapped = open(path + '.wrapped', 'w')
        # FIXME
        if name != 'iotjs':
            # fmodule_wrapped.write ("(function (a, b, c) {\n")
            fmodule_wrapped.write(
                "(function(exports, require, module) {\n")

        fmodule_wrapped.write(module)

        if name != 'iotjs':
            fmodule_wrapped.write("});\n")
            # fmodule_wrapped.write ("wwwwrap(a, b, c); });\n")
        fmodule_wrapped.close()

        # FIXME
        ret = subprocess.call([DUMPER,
                               '--save-snapshot-for-eval',
                               path + '.snapshot',
                               path + '.wrapped'])
        if ret != 0:
            msg = 'Failed to dump ' + path + (": - %d]" % (ret))
            print "%s%s%s" % ("\033[1;31m", msg, "\033[0m")
            exit(1)

        code = open(path + '.snapshot', 'r').read()

        fs.remove(path + '.wrapped')
        fs.remove(path + '.snapshot')

        for line in regroup(code, 8):
            buf = ', '.join(map(lambda ch: "0x{:02x}".format(ord(ch)), line))
            buf += ','
            writeLine(fout_cpp, buf, 1)
        writeLine(fout_cpp, '};')
        writeLine(fout_cpp,
                  'const int ' + name + '_l = sizeof(' + name + '_s);')



NATIVE_STRUCT1 = '''
struct native_mod {
const char* name;
const void* code;
const size_t length;
};

extern const struct native_mod natives[];
'''

NATIVE_STRUCT2 = '''
__attribute__ ((used)) const struct native_mod natives[] = {
'''

fout_h.write(NATIVE_STRUCT1)
fout_cpp.write(NATIVE_STRUCT2)
filenames = map(extractName, files)
for name in filenames:
    writeLine(fout_cpp,
              '{ ' + name + '_n, ' + name + '_s, ' + name + '_l },', 1)
writeLine(fout_cpp, '{ NULL, NULL, 0 }', 1)
writeLine(fout_cpp, '};')

fout_h.write(FOOTER1)
fout_cpp.write(FOOTER2)
