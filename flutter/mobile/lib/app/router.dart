import 'package:go_router/go_router.dart';

import '../features/auth/presentation/screens/auth_gate_screen.dart';
import '../features/groups/presentation/screens/group_selection_screen.dart';
import '../features/home/presentation/screens/group_home_screen.dart';

final GoRouter appRouter = GoRouter(
  initialLocation: '/',
  routes: <RouteBase>[
    GoRoute(
      path: '/',
      builder: (context, state) => const AuthGateScreen(),
    ),
    GoRoute(
      path: '/groups',
      builder: (context, state) => const GroupSelectionScreen(),
    ),
    GoRoute(
      path: '/group/:groupId',
      builder: (context, state) {
        final String groupId = state.pathParameters['groupId']!;
        return GroupHomeScreen(groupId: groupId);
      },
    ),
  ],
);
