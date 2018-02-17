#!/usr/bin/env python
# encoding: utf-8 

"""
retable() transforms list table to grid table.

The rst reader expects properly formated grid tables.
Displacing a ``|`` below will produce errors.
This file integrates https://github.com/nvie/vim-rst-tables to reformat tables,
to be used from Vim.

TODO test reformating the table below.

.. code:: python

    import docutils.statemachine
    import docutils.parsers.rst.tableparser

    text = '''
        +------------------------+------------+----------+----------+
        | Header row, column 1   | Header 2   | Header 3 | Header 4 |
        +========================+============+==========+==========+
        | body row 1, column 1   | column 2   | column 3 | column 4 |
        +------------------------+------------+----------+----------+
        | body row 2             |  Cells may span columns.         |
        +------------------------+------------+---------------------+
        | body row 3             | Cells may  | - Table cells       |
        +------------------------+ span rows. | - contain           |
        | body row 4             |            | - body elements.    |
        +------------------------+------------+---------------------+
    '''
    lines = filter(bool, (line.strip() for line in text.splitlines()))
    parser = docutils.parsers.rst.tableparser.GridTableParser()
    parser.parse(docutils.statemachine.StringList(list(lines)))

"""

import re
import textwrap
from untable import untable

title_all=list(r'''#*=-^~+_.,"'!$%&\\()/:;<>?@[\]`{|}''')
titlerex = re.compile('''^([#*=\-^~+_.,"'!$%&\\\(\)/:;<>?@\[\]`{|}])\\1+$''')
#retitle.match('====')
#retitle.match('\\\\\\')
#retitle.match('----')
#retitle.match('[[[[[[[')
#retitle.match('@@@@@@@')
#retitle.match('*******')

def join_rows(rows, sep='\n'):
    """Given a list of rows (a list of lists) this function returns a
    flattened list where each the individual columns of all rows are joined
    together using the line separator.

    """
    output = []
    for row in rows:
        # grow output array, if necessary
        if len(output) <= len(row):
            for i in range(len(row) - len(output)):
                output.extend([[]])

        for i, field in enumerate(row):
            field_text = field.strip()
            if field_text:
                output[i].append(field_text)
    return list(map(lambda lines: sep.join(lines), output))


def line_is_separator(line):
    return re.match('^[\t +=-]+$', line)


def has_line_seps(raw_lines):
    for line in raw_lines:
        if line_is_separator(line):
            return True
    return False


def partition_raw_lines(raw_lines):
    """Partitions a list of raw input lines so that between each partition, a
    table row separator can be placed.

    """
    if not has_line_seps(raw_lines):
        return list(map(lambda x: [x], raw_lines))

    curr_part = []
    parts = [curr_part]
    for line in raw_lines:
        if line_is_separator(line):
            curr_part = []
            parts.append(curr_part)
        else:
            curr_part.append(line)

    # remove any empty partitions (typically the first and last ones)
    return list(filter(lambda x: x != [], parts))


def unify_table(table):
    """Given a list of rows (i.e. a table), this function returns a new table
    in which all rows have an equal amount of columns.  If all full column is
    empty (i.e. all rows have that field empty), the column is removed.

    """
    max_fields = max(map(lambda row: len(row), table))
    empty_cols = [True] * max_fields
    output = []
    for row in table:
        curr_len = len(row)
        if curr_len < max_fields:
            row += [''] * (max_fields - curr_len)
        output.append(row)

        # register empty columns (to be removed at the end)
        for i in range(len(row)):
            if row[i].strip():
                empty_cols[i] = False

    # remove empty columns from all rows
    table = output
    output = []
    for row in table:
        cols = []
        for i in range(len(row)):
            should_remove = empty_cols[i]
            if not should_remove:
                cols.append(row[i])
        output.append(cols)

    return output


def split_table_row(row_string):
    # if "^| " or " | " or " |$" is found, this is already a table,
    # if not, then we're creating a table with double space
    if not re.search(r'^\|\s+|\s+\|\s+|\s+\|$', row_string):
        return re.split(r'\s\s+', row_string.rstrip())

    # strip off the outer table drawings ("^| " and " |$"), but not
    # "^|[^ ]" or "[^ ]|$" because they can be used in "|replacements|"
    row_string = re.sub(r'^\s*\|\s+|\s+\|\s*$', '', row_string)
    # split, not by "|" but by " | " so we can have "|replacements|"
    # inside columns as well
    return re.split(r'^\|\s+|\s+\|\s+|\s+\|$', row_string)


def parse_table(raw_lines):
    row_partition = partition_raw_lines(raw_lines)
    lines = list(map(
        (lambda row_string: join_rows(list(map(split_table_row, row_string)))),
        row_partition))
    return unify_table(lines)


def table_line(widths, header=False):
    if header:
        linechar = '='
    else:
        linechar = '-'
    sep = '+'
    parts = []
    for width in widths:
        parts.append(linechar * width)
    if parts:
        parts = [''] + parts + ['']
    return sep.join(parts)


def get_field_width(field_text):
    return max(map(lambda s: len(s), field_text.split('\n')))


def split_row_into_lines(row):
    row = list(map(lambda field: field.split('\n'), row))
    height = max(map(lambda field_lines: len(field_lines), row))
    turn_table = []
    for i in range(height):
        fields = []
        for field_lines in row:
            if i < len(field_lines):
                fields.append(field_lines[i])
            else:
                fields.append('')
        turn_table.append(fields)
    return turn_table


def get_column_widths(table):
    widths = []
    for row in table:
        num_fields = len(row)
        # dynamically grow
        if num_fields >= len(widths):
            widths.extend([0] * (num_fields - len(widths)))
        for i in range(num_fields):
            field_text = row[i]
            field_width = get_field_width(field_text)
            widths[i] = max(widths[i], field_width)
    return widths


def get_column_widths_from_border_spec(slice_):
    border = None
    for row in slice_:
        if line_is_separator(row):
            border = row.strip()
            break

    if border is None:
        raise RuntimeError(
            'Cannot reflow this table. Top table border not found.')

    left = right = None
    if border[0] == '+':
        left = 1
    if border[-1] == '+':
        right = -1
    return list(map(
        (lambda drawing: max(0, len(drawing) - 2)),
        border[left:right].split('+')))


def pad_fields(row, widths):
    """Pads fields of the given row, so each field lines up nicely with the
    others.

    """
    widths = list(map(lambda w: ' %-' + str(w) + 's ', widths))

    # Pad all fields using the calculated widths
    new_row = []
    for i in range(len(row)):
        col = row[i]
        col = widths[i] % col.strip()
        new_row.append(col)
    return new_row


def reflow_row_contents(row, widths):
    new_row = []
    for i, field in enumerate(row):
        wrapped_lines = textwrap.wrap(field.replace('\n', ' '), widths[i])
        new_row.append("\n".join(wrapped_lines))
    return new_row


def draw_table(indent, table, manual_widths=None, withheader=1):
    if table == []:
        return []

    if manual_widths is None:
        col_widths = get_column_widths(table)
    else:
        col_widths = manual_widths

    # Reserve room for the spaces
    sep_col_widths = list(map(lambda x: x + 2, col_widths))
    header_line = table_line(sep_col_widths, header=withheader)
    normal_line = table_line(sep_col_widths, header=False)

    output = [indent+normal_line]
    first = True
    for row in table:

        if manual_widths:
            row = reflow_row_contents(row, manual_widths)

        row_lines = split_row_into_lines(row)

        # draw the lines (num_lines) for this row
        for row_line in row_lines:
            row_line = pad_fields(row_line, col_widths)
            output.append(indent+"|".join([''] + row_line + ['']))

        # then, draw the separator
        if first:
            output.append(indent+header_line)
            first = False
        else:
            output.append(indent+normal_line)

    return output

def get_bounds(lines,row,col):
    upper = lower = row
    try:
        while upper>-1 and lines[upper].strip():
            upper -= 1
    except IndexError:
        pass
    else:
        upper += 1
    try:
        while lines[lower].strip():
            lower += 1
    except IndexError:
        lower -= 1
    else:
        lower -= 1
    match = re.match('^(\s*).*$', lines[upper])
    return (upper, lower, match.group(1))

def ReformatTable(lines,row,col,withheader):
    upper, lower, indent = get_bounds(lines,row,col)
    slice_ = lines[upper:lower+1]
    table = parse_table(slice_)
    slice_ = draw_table(indent, table, None, withheader)
    lines[upper:lower+1] = slice_

def ReflowTable(lines,row,col):
    upper, lower, indent = get_bounds(lines,row,col)
    slice_ = lines[upper:lower+1]
    withheader = 0
    for t in slice_:
        if '+==' in t:
            withheader = 1
            break
    widths = get_column_widths_from_border_spec(slice_)
    table = parse_table(slice_)
    slice_ = draw_table(indent, table, widths, withheader)
    lines[upper:lower+1] = slice_

def ReTitle(lines,row,col):
    upper, lower, indent = get_bounds(lines,row,col)
    t = None
    for i in range(upper,lower+1):
        if not titlerex.match(lines[i]):
            t = lines[i]
            break
    if t == None:
        return
    tstrip = t.strip()
    leni = len(tstrip)
    for j in range(upper,lower+1):
        if i==j: 
            lines[i] = tstrip
            continue
        if titlerex.match(lines[j]):
            lines[j] = lines[j][0]*leni

class doretable:
    def __init__(self):
        self.tbl = []
    def __call__(self,row,nColumns,org,islast,withheader):
        clls = [' '.join([ax.strip() for ax in x]) for x in row]
        self.tbl.append(' | '.join(clls))
        if islast:
            ReformatTable(self.tbl,0,0,withheader)
            yield from self.tbl
            del self.tbl[:]
            while org and not org[-1].strip():
                yield '\n'
                del org[-1]
        del org[:]

def retable(data):
    """transform listtable to gridtable"""
    drt = doretable()
    yield from untable(data,drt)

def main():
    import codecs
    import sys
    import argparse

    #'≥'.encode('cp1252') # UnicodeEncodeError on Windows, therefore...
    #makes problems with pdb, though
    sys.stdout = codecs.getwriter("utf-8")(sys.stdout.detach())
    sys.stdin = codecs.getreader("utf-8")(sys.stdin.detach())

    parser = argparse.ArgumentParser(description='''Reflow tables RST document.''')
    parser.add_argument('INPUT', type=argparse.FileType('r',encoding='utf-8'), nargs='+', help='RST file(s)')
    args = parser.parse_args()
    for infile in args.INPUT:
        data = infile.readlines()
        for ln in retable(data):
            sys.stdout.write(ln)

if __name__ == '__main__':
    main()

