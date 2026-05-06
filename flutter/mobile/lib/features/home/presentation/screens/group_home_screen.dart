import 'package:flutter/material.dart';

import '../../../dashboard/presentation/screens/dashboard_screen.dart';
import '../../../matches/presentation/screens/matches_screen.dart';
import '../../../players/presentation/screens/players_screen.dart';
import '../../../settings/presentation/screens/group_settings_screen.dart';

class GroupHomeScreen extends StatefulWidget {
  const GroupHomeScreen({
    required this.groupId,
    super.key,
  });

  final String groupId;

  @override
  State<GroupHomeScreen> createState() => _GroupHomeScreenState();
}

class _GroupHomeScreenState extends State<GroupHomeScreen> {
  int currentIndex = 0;

  @override
  Widget build(BuildContext context) {
    final List<Widget> pages = <Widget>[
      DashboardScreen(groupId: widget.groupId),
      MatchesScreen(groupId: widget.groupId),
      PlayersScreen(groupId: widget.groupId),
      GroupSettingsScreen(groupId: widget.groupId),
    ];

    return Scaffold(
      appBar: AppBar(
        title: Text('Grupo ${widget.groupId}'),
      ),
      body: IndexedStack(
        index: currentIndex,
        children: pages,
      ),
      bottomNavigationBar: NavigationBar(
        selectedIndex: currentIndex,
        onDestinationSelected: (int index) {
          setState(() {
            currentIndex = index;
          });
        },
        destinations: const <NavigationDestination>[
          NavigationDestination(
            icon: Icon(Icons.query_stats),
            label: 'Dashboard',
          ),
          NavigationDestination(
            icon: Icon(Icons.sports_soccer),
            label: 'Partidos',
          ),
          NavigationDestination(
            icon: Icon(Icons.group),
            label: 'Jugadores',
          ),
          NavigationDestination(
            icon: Icon(Icons.settings),
            label: 'Ajustes',
          ),
        ],
      ),
    );
  }
}
