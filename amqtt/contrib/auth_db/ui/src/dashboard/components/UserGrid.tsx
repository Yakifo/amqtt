import Grid from '@mui/material/Grid';
import Box from '@mui/material/Box';
import Stack from '@mui/material/Stack';
import Copyright from '../Copyright';
// @ts-ignore
import DescriptionPanel from "./DescriptionPanel";

export default function UserGrid() {

  return (
    <Box sx={{width: '100%', minWidth: {sm: '100%', md: '800px'}, maxWidth: {sm: '100%', md: '1700px'}}}>
      {/* cards */}

      <Grid
        container
        spacing={2}
        columns={12}
        sx={{mb: (theme) => theme.spacing(2)}}
      >
        <DescriptionPanel/>
      </Grid>
      <Grid
        container
        spacing={2}
        columns={12}
        sx={{mb: (theme) => theme.spacing(2)}}
      >
        <Grid size={{xs: 12, md: 12}}>

      </Grid>
        <Grid size={{xs: 12, md: 6}}>

        </Grid>
        <Grid size={{xs: 12, md: 6}}>

        </Grid>
        <Grid size={{xs: 12, md: 6}}>

        </Grid>
        <Grid size={{xs: 12, md: 6}}>

        </Grid>
        <Grid size={{xs: 12, md: 6}}>

        </Grid>
        <Grid size={{xs: 12, md: 6}}>

        </Grid>
      </Grid>

      <Grid container spacing={2} columns={12}>
        <Grid size={{xs: 12, lg: 9}}></Grid>
        <Grid size={{xs: 12, lg: 3}}>
          <Stack gap={2} direction={{xs: 'column', sm: 'row', lg: 'column'}}></Stack>
        </Grid>
      </Grid>
      <Copyright sx={{my: 4}}/>
    </Box>
  );
}
