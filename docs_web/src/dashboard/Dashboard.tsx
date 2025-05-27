import type {} from '@mui/x-date-pickers/themeAugmentation';
import type {} from '@mui/x-charts/themeAugmentation';
import type {} from '@mui/x-tree-view/themeAugmentation';
import { alpha } from '@mui/material/styles';
import CssBaseline from '@mui/material/CssBaseline';
import Box from '@mui/material/Box';
import Stack from '@mui/material/Stack';
import AppNavbar from './components/AppNavbar';

import MainGrid from './components/MainGrid';

import AppTheme from '../shared-theme/AppTheme';

import OtherLogo from './amqtt_bw.svg';

import {
  chartsCustomizations,
  treeViewCustomizations,
} from './theme/customizations';
import AppBar from "@mui/material/AppBar";
import {Toolbar} from "@mui/material";
import Typography from "@mui/material/Typography";

const xThemeComponents = {
  ...chartsCustomizations,
  ...treeViewCustomizations,
};

export default function Dashboard(props: { disableCustomTheme?: boolean }) {
  return (
    <AppTheme {...props} themeComponents={xThemeComponents}>
      <CssBaseline enableColorScheme />
      <AppBar position="static" elevation={6}>
        <Toolbar>
          <img
            src={OtherLogo}
            style={{width: 150}}
            alt="website logo"
          />

        </Toolbar>
      </AppBar>
      <Box sx={{display: 'flex'}}>
        <AppNavbar/>
        {/* Main content */}
        <Box
          component="main"
          sx={(theme) => ({
            flexGrow: 1,
            backgroundColor: theme.vars
              ? `rgba(${theme.vars.palette.background.defaultChannel} / 1)`
              : alpha(theme.palette.background.default, 1),
            overflow: 'auto',
          })}
        >
          <Stack
            spacing={2}
            sx={{
              alignItems: 'center',
              mx: 3,
              pb: 5,
              mt: { xs: 8, md: 0 },
            }}
          >
            <MainGrid />
          </Stack>
        </Box>
      </Box>
    </AppTheme>
  );
}
