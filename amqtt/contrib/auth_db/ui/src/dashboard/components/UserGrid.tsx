import Grid from '@mui/material/Grid';
import Box from '@mui/material/Box';
import Stack from '@mui/material/Stack';
import Copyright from '../Copyright';
import DescriptionPanel from "./DescriptionPanel";
import {type User, users} from "../../assets/users.ts";
import React, {useState} from "react";
import {DataGrid, type GridColDef, type GridRowId, GridToolbarContainer} from "@mui/x-data-grid";
import {Button, gridClasses, Toolbar} from "@mui/material";
import EditIcon from '@mui/icons-material/Edit'
import DeleteIcon from '@mui/icons-material/Delete'


const userDefault: User = {id: 0, username: '', publish_acl: [], subscribe_acl: [], receive_acl: []}


export default function UserGrid() {
  const [newUser, setNewUser] = useState<User>(userDefault);
  const [userRows, setUserRows] = useState<User[] | []>(users());

  const handleEdit = (id: GridRowId) => {
    console.log(`handle edit of ${id}`)
  };

  const handleDelete = (id: GridRowId) => {
    console.log(`handle delete of ${id}`)
  };

  const userHead: GridColDef[] = [
    {field: 'username', headerName: 'Username', type: 'string', width: 200},
    {field: 'publish_acl', headerName: 'Publish ACL', type: 'string', width: 200, sortable: false, hideable: false},
    {field: 'subscribe_acl', headerName: 'Subscribe ACL', type: 'string', width: 200, sortable: false, hideable: false},
    {field: 'receive_acl', headerName: 'Receive ACL', type: 'string', width: 200, sortable: false, hideable: false},
    {
      field: 'edit',
      headerName: '',
      type: 'action',
      width: 128,
      sortable: false,
      filterable: false,
      hideable: false,
      renderCell: params => (
        <Button onClick={() => handleEdit(params.id)} size="small" className='user-button-edit'>
          <EditIcon/>
        </Button>
      )
    },
    {
      field: 'delete',
      headerName: '',
      type: 'action',
      width: 128,
      sortable: false,
      filterable: false,
      hideable: false,
      renderCell: params => (
        <Button onClick={() => handleDelete(params.id)} size="small" className='user-button-delete'>
          <DeleteIcon/>
        </Button>
      )
    }
  ];

  return (
    <Box sx={{width: '100%', minWidth: {sm: '100%', md: '800px'}, maxWidth: {sm: '100%', md: '1700px'}}}>
      <Grid
        container
        spacing={2}
        columns={12}
        sx={{mb: (theme) => theme.spacing(2)}}
      >
      </Grid>
      <Grid
        container
        spacing={2}
        columns={12}
        sx={{mb: (theme) => theme.spacing(2)}}
      >
        <Grid size={{xs: 12, md: 12}}>
          <DataGrid
            rows={userRows}
            columns={userHead}
            disableColumnSelector
            rowHeight={72}
            columnHeaderHeight={48}
            autoHeight
            showToolbar
            slotProps={{
              toolbar: {
                printOptions: {disableToolbarButton: true},
                csvOptions: {disableToolbarButton: true},
              },
            }}
            initialState={{
              pagination: {
                paginationModel: {
                  pageSize: 10
                }
              }
            }}
            pageSizeOptions={[5, 10, 20]}
            disableRowSelectionOnClick
            sx={{
              '& .MuiDataGrid-columnHeader': {
                color: '#757575',
                fontSize: '14px',
                fontWeight: '500 !important',
                lineHeight: '16px !important',
                padding: '0 24px'
              },
              '& .MuiDataGrid-row': {
                maxHeight: '72px !important'
              },
              '& .MuiDataGrid-cell:focus-within': {
                outline: 'transparent'
              },
              '& .MuiDataGrid-columnHeader:focus-within': {
                outline: 'transparent'
              },
              '& .MuiButtonBase-root': {}
            }}
          />
        </Grid>
      </Grid>
      <Copyright sx={{my: 4}}/>
    </Box>
  );
}
