from datetime import datetime as dt
import dash
from dash.exceptions import PreventUpdate
import dash_daq as daq
import dash_table
import dash_html_components as html
import dash_core_components as dcc

from fastcounting import queries

external_stylesheets = ['https://codepen.io/chriddyp/pen/bWLwgP.css']
params = ['general', 'account', 'text', 'amount',
          'kontenseite', 'batchID', 'date']
params = ['account', 'text', 'amount', 'date', 'relations', 'general']

operators = [['ge ', '>='],
             ['le ', '<='],
             ['lt ', '<'],
             ['gt ', '>'],
             ['ne ', '!='],
             ['eq ', '='],
             ['contains '],
             ['datestartswith ']]

dropdown_options = queries.account_name_pairs()

theme = {'dark': True,
         'detail': '#007439',
         'primary': '#00EA64',
         'secondary': '#6E6E6E'}

# global state of our loaded data
df = None

app = dash.Dash(__name__, external_stylesheets=external_stylesheets)


app.layout = html.Div(children=[
    html.Div(className='row', children=[
        dcc.DatePickerRange(
            number_of_months_shown=3,
            clearable=True,
            id='my-date-picker-range',
            min_date_allowed=dt(1995, 8, 5),
            max_date_allowed=dt(2021, 9, 19),
            initial_visible_month=dt(2017, 8, 5),
            end_date=dt(2017, 8, 25).date(),
            className='three columns'),
        dcc.Dropdown(
            id='my-account-dropdown',
            options=dropdown_options,
            multi=True,
            className='seven columns'),
        daq.ToggleSwitch(
            color='#1a0013',
            style={'margin-left': '3%'},
            id='toggle-theme',
            label='Darkmode',
            labelPosition='bottom',
            value=True,
            className='one columns',
            size=50),
        ]),
    html.Br(),
    # context table
    dash_table.DataTable(
        id='context',
        columns=([{'id': p, 'name': p} for p in params]),
        data=[dict({param: 0 for param in params})]
        ),
    # you cant put this inside dark themes!
    dash_table.DataTable(
        id='table',
        columns=([{'id': p, 'name': p} for p in params]),
        data=[dict({param: 0 for param in params})],
        row_selectable='single',
        filter_action='custom',
        filter_query=''),
])


# context
@app.callback(
    [dash.dependencies.Output('context', 'columns'),
     dash.dependencies.Output('context', 'data')],
    [dash.dependencies.Input('table', 'selected_rows')])
def load_update_context(selected_row):
    if selected_row is not None and df is not None:
        format_columns = [{"name": i, "id": i} for i in params]
        generalid = df.iloc[selected_row[0]:selected_row[0]+1]['general']
        data = queries.general_context(int(generalid))
        return format_columns, data
    else:
        raise PreventUpdate


# filter
def filter_table(dff, filter):
    filtering_expressions = filter.split(' && ')
    for filter_part in filtering_expressions:
        col_name, operator, filter_value = split_filter_part(filter_part)

        if operator in ('eq', 'ne', 'lt', 'le', 'gt', 'ge'):
            # these operators match pandas series operator method names
            dff = dff.loc[getattr(dff[col_name], operator)(filter_value)]
        elif operator == 'contains':
            dff = dff.loc[dff[col_name].str.contains(filter_value, case=False)]
        elif operator == 'datestartswith':
            # this is a simplification of the front-end filtering logic,
            # only works with complete fields in standard format
            dff = dff.loc[dff[col_name].str.startswith(filter_value)]
    return dff


# atomic and account view
@app.callback(
    [dash.dependencies.Output('table', 'columns'),
     dash.dependencies.Output('table', 'data')],
    [dash.dependencies.Input('my-account-dropdown', 'value'),
     dash.dependencies.Input('my-date-picker-range', 'start_date'),
     dash.dependencies.Input('my-date-picker-range', 'end_date'),
     dash.dependencies.Input('table', "filter_query")])
def load_update_date(accounts, start_date, end_date, filter):
    print(filter)
    # number of max returns when we dont specify an account
    count = None
    streamdata = []
    if accounts:
        for account in accounts:
            if start_date and end_date:
                start, end = queries.string_parser(start_date, end_date)
                streamdata += queries.query_accountview(
                    account, start, end, count)
            else:
                streamdata += queries.query_accountview(
                    account=account, count=count)

    elif start_date and end_date:
        start, end = queries.string_parser(start_date, end_date)
        streamdata = queries.query_atomicview(start, end, count)
    else:
        raise PreventUpdate

    # format and sort data and return
    global df
    if streamdata:
        df = queries.stream_to_dataframe(streamdata)
        # since we have pontentially multiple accounts we need to sort it here.
        df['general'] = df['general'].astype(int)
        df.sort_values('general', inplace=True)
        # subset data if you want all data for debugging outcomment this:
        df = df[params]
        # filter dasta
        df = filter_table(df, filter)
        format_columns = [{"name": i, "id": i} for i in df.columns]
        return format_columns, df.to_dict('records')
    else:
        df = None
        # epmty data format for plotly html tables
        format_columns = [{"name": i, "id": i} for i in params]
        return format_columns, []


# backend based filtering, here we parse the plotly filter language.
def split_filter_part(filter_part):
    for operator_type in operators:
        for operator in operator_type:
            if operator in filter_part:
                name_part, value_part = filter_part.split(operator, 1)
                name = name_part[name_part.find('{') + 1: name_part.rfind('}')]

                value_part = value_part.strip()
                v0 = value_part[0]
                if (v0 == value_part[-1] and v0 in ("'", '"', '`')):
                    value = value_part[1: -1].replace('\\' + v0, v0)
                else:
                    try:
                        value = float(value_part)
                    except ValueError:
                        value = value_part

                # word operators need spaces after them in the filter string,
                # but we don't want these later
                return name, operator_type[0].strip(), value

    return [None] * 3


# dark theme table
@app.callback(
    [dash.dependencies.Output('table',  'style_header'),
     dash.dependencies.Output('table', 'style_cell'),
     dash.dependencies.Output('table', 'style_data_conditional')],
    [dash.dependencies.Input('toggle-theme', 'value')])
def switch_bg_table(dark):
    """To do create index like generalid which has no wholes."""
    if(dark):
        style_cell = {
            'backgroundColor': '#330026',
            'color': 'white'}
        style_header = {'backgroundColor': '#1a0013'}
        style_data_conditional = [
            {'if': {'filter_query': "{generalID} is odd"},
             'backgroundColor': '#4d0039',
             'color': 'white'}]
    else:
        style_cell = {
            'backgroundColor': 'white',
            'color': 'black'}
        style_header = {'backgroundColor': 'white'}
        style_data_conditional = [
            {'if': {'filter_query': "{generalID} is odd"},
             'backgroundColor': '#ffe6f9',
             'color': 'black'}]
    return [style_header, style_cell, style_data_conditional]


if __name__ == '__main__':
    app.run_server(debug=True)
