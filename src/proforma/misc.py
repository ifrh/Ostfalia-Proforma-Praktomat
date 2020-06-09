# -*- coding: utf-8 -*-

# This file is part of Ostfalia-Praktomat.
#
# Copyright (C) 2012-2019 Ostfalia University (eCULT-Team)
# http://ostfalia.de/cms/de/ecult/
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, see <http://www.gnu.org/licenses/>.
#

# collection of different functions

import VERSION

# string format for exception return message in HTTP
def get_http_error_page(title, message, callstack):
    return """%s

    %s

Praktomat: %s

Callstack:
    %s""" % (title, message, VERSION.version, callstack)