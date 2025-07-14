import Grid from "@mui/material/Grid";
import Typography from "@mui/material/Typography";

export default function DescriptionPanel() {
  return <>
  <Grid size={{xs: 12, md: 12}}>
          <Typography component="h2" variant="h6" sx={{mb: 2}}>
            User Administration
          </Typography>
          <div>
            content here
          </div>
        </Grid>
  </>
}