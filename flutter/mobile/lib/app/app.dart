import 'package:flutter/material.dart';

import '../core/theme/app_theme.dart';
import 'router.dart';

class FulbitoStatsApp extends StatelessWidget {
  const FulbitoStatsApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp.router(
      debugShowCheckedModeBanner: false,
      title: 'Fulbito Stats',
      theme: AppTheme.light(),
      routerConfig: appRouter,
    );
  }
}
